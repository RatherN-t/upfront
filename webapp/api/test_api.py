"""
Marketplace API tests — full flow against the simulated gateway.

No network. These prove the app's own logic (eligibility, funding-round
arithmetic, clamping, idempotent onboarding) and prove the adapter converts
Pinch-shaped JSON into a priced book. They prove NOTHING about whether the
live Pinch API behaves as expected — only a real test-mode call does that.
See docs/10-get-credentials-now.md.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# Point the DB at a scratch file before anything imports db.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["UPFRONT_DB"] = _TMP.name

import db                                    # noqa: E402
import main                                   # noqa: E402
from fastapi.testclient import TestClient     # noqa: E402
from pinch_gateway import (                   # noqa: E402
    BookProfile, SimulatedGateway, build_gateway)
from underwriting import summarise_returns    # noqa: E402

# Force the simulator regardless of ambient credentials so the suite is
# deterministic and never spends a real API call.
main.GATEWAY = SimulatedGateway()


ONBOARD = {
    "sector": "E-bike subscription rentals",
    "asset_class": "contract",
    "ticket_dollars": 34.78,
    "cadence": "weekly",
    "customers": 120,
    "term_weeks": 26,
}


def _wait_ready(client, tries: int = 200):
    """Onboarding runs on a background thread; poll until it settles."""
    import time
    for _ in range(tries):
        me = client.get("/api/business/me").json()
        if me["status"] in ("ready", "failed", "not_fundable"):
            return me
        time.sleep(0.05)
    raise AssertionError("onboarding did not settle")


class TestMoney(unittest.TestCase):
    def test_money_c_rejects_non_numbers(self):
        with self.assertRaises(TypeError):
            db.money_c("100")
        with self.assertRaises(TypeError):
            db.money_c(True)

    def test_money_c_rounds_to_int_cents(self):
        self.assertEqual(db.money_c(34.78), 3478)
        self.assertEqual(db.money_c(0.1 + 0.2), 30)   # float noise must not leak
        self.assertIsInstance(db.money_c(10), int)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            db.money_c(-1)


class TestProfile(unittest.TestCase):
    def test_rejects_float_ticket(self):
        with self.assertRaises(TypeError):
            BookProfile(name="x", sector="s", asset_class="contract",
                        ticket_c=34.78, cadence="weekly", customers=10)

    def test_rejects_unknown_asset_class(self):
        with self.assertRaises(ValueError):
            BookProfile(name="x", sector="s", asset_class="receivable",
                        ticket_c=3478, cadence="weekly", customers=10)

    def test_simulated_merchant_id_is_stable_across_restarts(self):
        """The demo must not drift. A fresh gateway (as after a server
        restart) must hand the same business the same merchant id, and
        therefore the same book."""
        p = BookProfile(name="Voltride", sector="e", asset_class="contract",
                        ticket_c=3478, cadence="weekly", customers=120,
                        seed_key="ops@voltride.example")
        a = SimulatedGateway().create_managed_merchant(
            p, email="ops@voltride.example")["id"]
        g = SimulatedGateway()
        g.create_managed_merchant(p, email="someone-else@x.test")  # bump state
        b = g.create_managed_merchant(p, email="ops@voltride.example")["id"]
        self.assertEqual(a, b)

    def test_different_businesses_get_different_books(self):
        g = SimulatedGateway()
        p = BookProfile(name="A", sector="e", asset_class="contract",
                        ticket_c=3478, cadence="weekly", customers=50)
        self.assertNotEqual(
            g.create_managed_merchant(p, email="a@x.test")["id"],
            g.create_managed_merchant(p, email="b@x.test")["id"])

    def test_same_seed_key_is_reproducible(self):
        a = BookProfile(name="x", sector="s", asset_class="contract",
                        ticket_c=3478, cadence="weekly", customers=10,
                        seed_key="a@b.c")
        b = BookProfile(name="x", sector="s", asset_class="contract",
                        ticket_c=3478, cadence="weekly", customers=10,
                        seed_key="a@b.c")
        self.assertEqual(a.gross_dishonour, b.gross_dishonour)
        self.assertEqual(a.trading_months, b.trading_months)


class TestSimulatorRealism(unittest.TestCase):
    """The simulator feeds the eligibility screen; if its history is
    unrealistic the screen rejects a healthy book. This caught a real bug:
    scattering hard dishonour codes across a long history flagged nearly
    every payer as hard-fail."""

    def test_hard_fail_payers_stay_a_small_cohort(self):
        from pinch_gateway import _synthesise_pull
        sys.path.insert(0, str(_HERE.parent.parent / "integration"))
        from adapter import hard_fail_payers

        p = BookProfile(name="Voltride", sector="e-bike",
                        asset_class="contract", ticket_c=3478,
                        cadence="weekly", customers=120, seed_key="v@x.test")
        pull = _synthesise_pull("mch_test01", p)
        flagged = hard_fail_payers(pull["processed_payments"])
        self.assertLess(len(flagged), p.customers * 0.15,
                        "hard-fail cohort should stay small; a long history "
                        "must not mark most of the book terminal")

    def test_most_of_a_healthy_book_is_eligible(self):
        from pinch_gateway import _synthesise_pull
        sys.path.insert(0, str(_HERE.parent.parent / "engine"))
        sys.path.insert(0, str(_HERE.parent.parent / "integration"))
        from adapter import book_from_pull
        from pricing_engine import screen

        p = BookProfile(name="Voltride", sector="e-bike",
                        asset_class="contract", ticket_c=3478,
                        cadence="weekly", customers=120, seed_key="v@x.test")
        pull = _synthesise_pull("mch_test01", p)
        book = book_from_pull(pull, name="V", sector="e",
                              asset_class="contract")
        s = screen(book)
        ratio = s["eligible_face_c"] / s["gross_face_c"]
        self.assertGreater(ratio, 0.70,
                           f"only {ratio:.0%} of a healthy book was eligible")


class TestFlow(unittest.TestCase):
    def setUp(self):
        db.reset_db()
        main.GATEWAY = SimulatedGateway()
        self.biz = TestClient(main.app)
        self.inv = TestClient(main.app)

    def _onboard_business(self, email="ops@voltride.test"):
        r = self.biz.post("/api/business/start",
                          json={"name": "Voltride", "email": email})
        self.assertEqual(r.status_code, 200)
        r = self.biz.post("/api/business/onboard", json=ONBOARD)
        self.assertEqual(r.status_code, 200)
        return _wait_ready(self.biz)

    def test_health_reports_mode(self):
        r = self.biz.get("/api/health").json()
        self.assertIn(r["pinch_mode"], ("live", "simulated"))
        self.assertTrue(r["pinch_mode_note"])

    def test_onboarding_produces_a_fundable_priced_book(self):
        me = self._onboard_business()
        self.assertEqual(me["status"], "ready", me["status_detail"])
        pricing = me["pricing"]
        self.assertTrue(pricing["fundable"])
        self.assertIn(pricing["rail_score"], ["A", "A-", "B+", "B", "C"])
        self.assertGreater(pricing["scan"]["attempts"], 100)
        self.assertGreater(pricing["cash_today_c"], 0)
        self.assertTrue(me["mch_id"].startswith("mch_"))

    def test_advance_never_exceeds_net_settled(self):
        me = self._onboard_business()
        p = me["pricing"]
        self.assertLessEqual(p["cash_today_c"], p["net_settled_c"],
                             "advancing more than what actually settles would "
                             "push Pinch fees silently onto investors")
        self.assertLessEqual(p["eligible_face_c"], p["gross_face_c"])

    def test_returns_always_carry_their_downside(self):
        me = self._onboard_business()
        r = me["pricing"]["returns"]
        for k in ("mean", "p5", "p1", "prob_loss"):
            self.assertIn(k, r)
        self.assertLessEqual(r["p5"], r["mean"])
        self.assertLessEqual(r["p1"], r["p5"])

    def test_onboarding_twice_reuses_the_managed_merchant(self):
        me = self._onboard_business()
        first = me["mch_id"]
        r = self.biz.post("/api/business/onboard", json=ONBOARD)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("reused_merchant"), first)
        again = _wait_ready(self.biz)
        self.assertEqual(again["mch_id"], first,
                         "a second onboarding must not create a second "
                         "managed merchant on Pinch")

    def test_open_round_then_invest(self):
        me = self._onboard_business()
        target = me["pricing"]["cash_today_c"]

        r = self.biz.post("/api/business/open-round",
                          json={"deadline_days": 7, "min_ticket_dollars": 50})
        self.assertEqual(r.status_code, 200)
        deal_id = r.json()["deal_id"]
        self.assertEqual(r.json()["target_c"], target)

        deals = self.inv.get("/api/deals").json()["deals"]
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["id"], deal_id)
        self.assertIn("returns", deals[0])

        self.inv.post("/api/investor/start",
                      json={"name": "Ari", "email": "ari@example.test"})
        r = self.inv.post("/api/invest",
                          json={"deal_id": deal_id, "amount_dollars": 500})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["accepted_c"], 50000)
        self.assertTrue(body["payment_link"]["url"])

        detail = self.inv.get(f"/api/deals/{deal_id}").json()
        self.assertEqual(detail["deal"]["raised_c"], 50000)
        self.assertEqual(len(detail["investments"]), 1)

    def test_second_round_blocked_while_one_is_open(self):
        self._onboard_business()
        self.biz.post("/api/business/open-round",
                      json={"deadline_days": 7, "min_ticket_dollars": 50})
        r = self.biz.post("/api/business/open-round",
                          json={"deadline_days": 7, "min_ticket_dollars": 50})
        self.assertEqual(r.status_code, 409)

    def test_below_minimum_ticket_is_rejected(self):
        self._onboard_business()
        r = self.biz.post("/api/business/open-round",
                          json={"deadline_days": 7, "min_ticket_dollars": 100})
        deal_id = r.json()["deal_id"]
        self.inv.post("/api/investor/start",
                      json={"name": "Ari", "email": "ari@example.test"})
        r = self.inv.post("/api/invest",
                          json={"deal_id": deal_id, "amount_dollars": 20})
        self.assertEqual(r.status_code, 409)

    def test_investment_clamps_to_remaining_and_funds_the_deal(self):
        me = self._onboard_business()
        target = me["pricing"]["cash_today_c"]
        r = self.biz.post("/api/business/open-round",
                          json={"deadline_days": 7, "min_ticket_dollars": 50})
        deal_id = r.json()["deal_id"]

        self.inv.post("/api/investor/start",
                      json={"name": "Whale", "email": "whale@example.test"})
        # ask for far more than the round needs
        r = self.inv.post("/api/invest",
                          json={"deal_id": deal_id,
                                "amount_dollars": target / 100 * 5})
        body = r.json()
        self.assertTrue(body["clamped"])
        self.assertEqual(body["accepted_c"], target,
                         "a round must never raise more than its target")

        detail = self.inv.get(f"/api/deals/{deal_id}").json()
        self.assertEqual(detail["deal"]["status"], "funded")
        self.assertEqual(self.inv.get("/api/deals").json()["deals"], [],
                         "a funded deal must leave the open marketplace")

    def test_cannot_invest_in_a_funded_deal(self):
        me = self._onboard_business()
        target = me["pricing"]["cash_today_c"]
        deal_id = self.biz.post(
            "/api/business/open-round",
            json={"deadline_days": 7, "min_ticket_dollars": 50}
        ).json()["deal_id"]
        self.inv.post("/api/investor/start",
                      json={"name": "Whale", "email": "whale@example.test"})
        self.inv.post("/api/invest", json={"deal_id": deal_id,
                                           "amount_dollars": target / 100})
        r = self.inv.post("/api/invest", json={"deal_id": deal_id,
                                               "amount_dollars": 100})
        self.assertEqual(r.status_code, 409)

    def test_auth_is_enforced_per_role(self):
        anon = TestClient(main.app)
        self.assertEqual(anon.get("/api/business/me").status_code, 401)
        self.assertEqual(anon.get("/api/investor/me").status_code, 401)
        self.assertEqual(
            anon.post("/api/invest",
                      json={"deal_id": 1, "amount_dollars": 10}).status_code, 401)
        # a business session must not be usable as an investor session
        self.biz.post("/api/business/start",
                      json={"name": "V", "email": "v@x.test"})
        self.assertEqual(self.biz.get("/api/investor/me").status_code, 401)

    def test_open_round_before_underwriting_is_rejected(self):
        self.biz.post("/api/business/start",
                      json={"name": "V", "email": "new@x.test"})
        r = self.biz.post("/api/business/open-round",
                          json={"deadline_days": 7, "min_ticket_dollars": 50})
        self.assertEqual(r.status_code, 409)


class TestSecurity(unittest.TestCase):
    def setUp(self):
        db.reset_db()
        main.GATEWAY = SimulatedGateway()
        self.client = TestClient(main.app)

    def test_expired_session_is_rejected(self):
        import sqlite3
        from datetime import datetime, timedelta, timezone
        self.client.post("/api/business/start",
                         json={"name": "V", "email": "v@x.test"})
        self.assertEqual(self.client.get("/api/business/me").status_code, 200)

        stale = (datetime.now(timezone.utc)
                 - timedelta(hours=db.SESSION_TTL_HOURS + 1)).isoformat()
        with db.connect() as c:
            c.execute("UPDATE sessions SET created_at=?", (stale,))

        self.assertEqual(self.client.get("/api/business/me").status_code, 401,
                         "a session past its TTL must not authenticate")

    def test_expired_session_row_is_removed(self):
        from datetime import datetime, timedelta, timezone
        r = self.client.post("/api/business/start",
                             json={"name": "V", "email": "v@x.test"})
        stale = (datetime.now(timezone.utc)
                 - timedelta(hours=db.SESSION_TTL_HOURS + 1)).isoformat()
        with db.connect() as c:
            c.execute("UPDATE sessions SET created_at=?", (stale,))
            token = c.execute("SELECT token FROM sessions").fetchone()["token"]
        db.get_session(token)
        with db.connect() as c:
            left = c.execute("SELECT COUNT(*) n FROM sessions").fetchone()["n"]
        self.assertEqual(left, 0)

    def test_sign_out_invalidates_the_session(self):
        self.client.post("/api/business/start",
                         json={"name": "V", "email": "v@x.test"})
        self.assertEqual(self.client.get("/api/business/me").status_code, 200)
        self.client.post("/api/sign-out")
        self.assertEqual(self.client.get("/api/business/me").status_code, 401)

    def test_onboarding_failure_does_not_leak_internal_detail(self):
        """A failing gateway must not echo upstream API bodies to the client.

        PinchError carries the response body and URL, so returning str(exc)
        would expose Pinch payloads to anyone polling their own status.
        """
        class Boom:
            mode = "live"

            def create_managed_merchant(self, *a, **k):
                raise RuntimeError(
                    "HTTP 401 on https://api.getpinch.com.au/test/merchants/"
                    "managed: {'secret':'sk_test_super_secret','token':'eyJhbG'}")

        main.GATEWAY = Boom()
        self.client.post("/api/business/start",
                         json={"name": "V", "email": "v@x.test"})
        self.client.post("/api/business/onboard", json=ONBOARD)
        me = _wait_ready(self.client)

        self.assertEqual(me["status"], "failed")
        detail = me["status_detail"]
        for leak in ("sk_test", "eyJhbG", "getpinch.com.au", "secret"):
            self.assertNotIn(leak, detail,
                             f"internal detail leaked to client: {detail!r}")
        self.assertIn("RuntimeError", detail, "error class is still useful")


class TestSummarise(unittest.TestCase):
    def test_empty_distribution_is_zeroed_not_missing(self):
        r = summarise_returns({})
        self.assertEqual(set(r), {"mean", "p5", "p1", "prob_loss"})


class TestPercentileCurve(unittest.TestCase):
    """The chart and the headline numbers must be the same computation.

    If the curve is derived differently from p5/p1, the two can drift and the
    page ends up quoting a downside its own chart contradicts.
    """

    def setUp(self):
        db.reset_db()
        main.GATEWAY = SimulatedGateway()
        self.client = TestClient(main.app)

    def test_curve_agrees_with_quoted_percentiles(self):
        self.client.post("/api/business/start",
                         json={"name": "Voltride", "email": "v@x.test"})
        self.client.post("/api/business/onboard", json=ONBOARD)
        me = _wait_ready(self.client)
        self.assertEqual(me["status"], "ready", me["status_detail"])

        pricing = me["pricing"]
        curve = {pt["p"]: pt["value"] for pt in pricing["curve"]}
        self.assertEqual(len(curve), 99)
        self.assertAlmostEqual(curve[5], pricing["returns"]["p5"], places=9)
        self.assertAlmostEqual(curve[1], pricing["returns"]["p1"], places=9)

    def test_curve_is_monotonic(self):
        from underwriting import percentile_curve
        import random
        rng = random.Random(3)
        xs = [rng.gauss(0.1, 0.05) for _ in range(2000)]
        vals = [pt["value"] for pt in percentile_curve(xs)]
        self.assertEqual(vals, sorted(vals),
                         "a percentile curve must never go down as p rises")

    def test_empty_samples_give_empty_curve(self):
        from underwriting import percentile_curve
        self.assertEqual(percentile_curve([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
