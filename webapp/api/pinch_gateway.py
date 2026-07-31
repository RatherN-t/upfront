"""
Pinch gateway — one interface, two honest implementations.
==========================================================

`LiveGateway` makes real Pinch API calls through `integration/pinch_client.py`.
`SimulatedGateway` produces Pinch-*shaped* JSON in process, so the product is
demonstrable with no credentials at all.

Both return the same shapes, which means `integration/adapter.py` converts
either one into an engine `Book` with no branching — the simulator exercises
the same adapter code path the live integration uses, so a passing simulated
run is real evidence about the adapter, and no evidence at all about Pinch.

**The mode is never hidden.** Every gateway reports `.mode`, every response
carries it, the API returns it, and the UI displays it. A demo that claims a
live integration while quietly running a simulator is the fastest way to lose
a judge's trust, and "here is the real code path, here is the graceful
fallback" is a better answer than a fake one. Do not add a flag that makes
the simulator claim to be live.
"""

from __future__ import annotations

import hashlib
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "integration"))
sys.path.insert(0, str(_ROOT / "engine"))

MODE_LIVE = "live"
MODE_SIMULATED = "simulated"

HARD_CODES = ["blocked-by-bank", "invalid-account", "invalid-card"]
SOFT_CODES = ["insufficient-funds", "insufficient-funds", "temporary-problem"]

# Live seeding makes one HTTP call per payment. A full 26-week book across
# dozens of payers is thousands of calls and minutes of wall time, so the
# live path seeds a smaller representative history and reads it back. The
# forward schedule comes from a Plan, which is a handful of calls regardless.
LIVE_SEED_PAYERS = 12
# Pinch rejects a transactionDate more than 30 days in the past, so the
# back-dated history cannot reach further than four weekly cycles.
LIVE_SEED_WEEKS = 4


class GatewayError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Business profile — what onboarding answers turn into
# ---------------------------------------------------------------------------

class BookProfile:
    """The shape of a business's book, derived from its onboarding answers.

    Risk characteristics (dishonour rate, cure rate, hard-fail share) are NOT
    asked of the business — the entire product thesis is that these are
    observed from the payment rail rather than self-reported. Here they are
    drawn from a generator seeded on the business's own identity, so each
    business gets a distinct but reproducible profile.
    """

    def __init__(self, *, name: str, sector: str, asset_class: str,
                 ticket_c: int, cadence: str, customers: int,
                 term_weeks: int = 26, seed_key: str = ""):
        if not isinstance(ticket_c, int) or isinstance(ticket_c, bool):
            raise TypeError("ticket_c must be integer cents")
        if asset_class not in ("contract", "invoice"):
            raise ValueError("asset_class must be 'contract' or 'invoice'")
        self.name = name
        self.sector = sector
        self.asset_class = asset_class
        self.ticket_c = max(100, ticket_c)
        self.cadence = cadence if cadence in ("weekly", "fortnightly", "monthly") else "weekly"
        self.customers = max(1, min(customers, 400))
        self.term_weeks = max(4, min(term_weeks, 26))

        rng = random.Random(
            int(hashlib.sha256((seed_key or name).encode()).hexdigest()[:12], 16))
        self.rng = rng

        # Smaller tickets dishonour more often; invoices dishonour more than
        # mandated subscriptions. Both effects are real and both are visible
        # in the fee-drag maths the engine already does.
        small = 1.0 if self.ticket_c > 5000 else 1.35
        klass = 1.6 if asset_class == "invoice" else 1.0
        self.gross_dishonour = min(0.20, rng.uniform(0.035, 0.085) * small * klass)
        self.cure_rate = rng.uniform(0.52, 0.74)
        self.hard_share = rng.uniform(0.16, 0.32)
        self.trading_months = rng.choice([11, 14, 19, 24, 28, 31, 40, 48])
        # Adversely selected population, not the economy-wide base rate.
        # See docs/00-decisions.md D8.
        self.business_pd_annual = rng.uniform(0.035, 0.090)

    @property
    def weeks_between(self) -> int:
        return {"weekly": 1, "fortnightly": 2, "monthly": 4}[self.cadence]

    @property
    def n_installments(self) -> int:
        return max(1, self.term_weeks // self.weeks_between)

    def history_attempts(self) -> int:
        """How many past attempts this business would have on the rail."""
        cycles = max(6, int(self.trading_months * 4.33 / self.weeks_between))
        return min(9000, self.customers * cycles)

    def summary(self) -> dict:
        return {
            "name": self.name, "sector": self.sector,
            "asset_class": self.asset_class, "ticket_c": self.ticket_c,
            "cadence": self.cadence, "customers": self.customers,
            "term_weeks": self.term_weeks,
            "trading_months": self.trading_months,
        }


# ---------------------------------------------------------------------------
# Simulated gateway
# ---------------------------------------------------------------------------

class SimulatedGateway:
    """Emits Pinch-shaped JSON without touching the network."""

    mode = MODE_SIMULATED

    def __init__(self) -> None:
        self._books: dict[str, BookProfile] = {}
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_sim{self._counter:08d}"

    def create_managed_merchant(self, profile: BookProfile, *,
                                email: str = "", **_: Any) -> dict:
        # Derived from the business's identity, not a process-global counter:
        # the same business must produce the same merchant id, and therefore
        # the same book, on every run. A counter drifts whenever the server
        # restarts, and a demo that changes its numbers between rehearsal and
        # stage is worse than no demo.
        h = hashlib.sha256((email or profile.name).encode()).hexdigest()[:10]
        mch = f"mch_sim{h}"
        self._books[mch] = profile
        return {
            "id": mch,
            "testMerchantId": mch.replace("mch_", "mch_test_"),
            "testOnlyMerchant": True,
            "companyName": profile.name,
            "compliance": {"status": "new", "liveEnabled": False,
                           "transactionsEnabled": False,
                           "settlementsEnabled": False},
            "_mode": self.mode,
        }

    def seed_book(self, mch_id: str, profile: BookProfile) -> dict:
        self._books[mch_id] = profile
        return {"seeded": True, "mode": self.mode,
                "attempts": profile.history_attempts()}

    def pull_book(self, mch_id: str, profile: Optional[BookProfile] = None) -> dict:
        profile = profile or self._books.get(mch_id)
        if profile is None:
            raise GatewayError(f"no simulated book for {mch_id}")
        return _synthesise_pull(mch_id, profile)

    def create_payment_link(self, *, amount_c: int, description: str,
                            metadata: Optional[dict] = None) -> dict:
        if not isinstance(amount_c, int) or isinstance(amount_c, bool):
            raise TypeError("amount_c must be integer cents")
        pl = self._next_id("pl")
        return {"id": pl,
                "url": f"https://pay.getpinch.com.au/simulated/{pl}",
                "amount": amount_c, "description": description,
                "_mode": self.mode}


def synthesise_attempts(mch_id: str, profile: BookProfile,
                        rng: Optional[random.Random] = None,
                        payer_ids: Optional[list[str]] = None) -> list[dict]:
    """Pinch-shaped `GET /payments/processed` records for a book's history.

    Used in two places. The simulator uses it for everything. The live path
    uses it ONLY when a real merchant has no settled payments yet — Pinch's
    test-mode settlement runs on its own batch, so a freshly seeded sandbox
    account has a real forward book and an empty history for days.

    Whoever calls this must label the result. An assumed history presented as
    a measured one is the single most damaging thing this codebase could do.
    """
    rng = rng or random.Random(
        int(hashlib.sha256(f"{mch_id}:{profile.name}".encode()).hexdigest()[:12], 16))
    today = date.today()
    cure_within_soft = min(0.99, profile.cure_rate / max(1e-9, 1 - profile.hard_share))
    n_hist = profile.history_attempts()

    ids = payer_ids or [f"pyr_{mch_id[-6:]}_{i:04d}"
                        for i in range(profile.customers)]

    # A hard dishonour is terminal for that payer's mandate — the customer
    # churns off the book rather than paying for another two years. So hard
    # codes belong to a small cohort, not scattered across everyone: over a
    # long history, random scattering flags nearly every payer as hard-fail
    # and the eligibility screen then rejects most of a healthy book.
    n_hard_payers = max(1, int(len(ids) * rng.uniform(0.03, 0.07)))
    hard_cohort = set(rng.sample(ids, min(n_hard_payers, len(ids))))
    hard_emitted: set[str] = set()

    processed: list[dict] = []
    for i in range(n_hist):
        payer_id = ids[i % len(ids)]
        amt = max(100, int(rng.gauss(profile.ticket_c, profile.ticket_c * 0.35)))
        when = (today - timedelta(weeks=rng.randint(1, 100))).isoformat()

        if rng.random() < profile.gross_dishonour:
            # only the cohort can hard-fail, and only once
            if payer_id in hard_cohort and payer_id not in hard_emitted:
                hard_emitted.add(payer_id)
                attempts = [{"id": f"att_{i}_0", "status": "dishonoured",
                             "amount": amt, "transactionDate": when,
                             "dishonour": {"code": rng.choice(HARD_CODES)}}]
            else:
                attempts = [{"id": f"att_{i}_0", "status": "dishonoured",
                             "amount": amt, "transactionDate": when,
                             "dishonour": {"code": rng.choice(SOFT_CODES)}}]
                if rng.random() < cure_within_soft:
                    # retry settled — the scanner reads this as a cure
                    attempts.append({"id": f"att_{i}_1", "status": "settled",
                                     "amount": amt, "transactionDate": when})
        else:
            attempts = [{"id": f"att_{i}_0", "status": "settled",
                         "amount": amt, "transactionDate": when}]

        processed.append({
            "id": f"pmt_{mch_id[-6:]}_{i:05d}", "amount": amt,
            "transactionDate": when, "payer": {"id": payer_id},
            "attempts": attempts,
        })
    return processed


def _synthesise_pull(mch_id: str, profile: BookProfile) -> dict:
    """Build a Pinch-shaped pull_book() response.

    Shapes here must match what `integration/adapter.py` reads: payments with
    an `attempts[]` array carrying status/amount/dishonour, and subscriptions
    carrying a payer, a planId, and an embedded `payments` schedule.
    """
    rng = random.Random(
        int(hashlib.sha256(f"{mch_id}:{profile.name}".encode()).hexdigest()[:12], 16))
    today = date.today()

    processed = synthesise_attempts(mch_id, profile, rng)

    # --- forward schedule (GET /subscriptions + calculated-payments) ---
    plan_id = f"pln_{mch_id[-6:]}_0001"
    step = profile.weeks_between
    schedule = [
        {"amount": profile.ticket_c,
         "transactionDate": (today + timedelta(weeks=(k + 1) * step)).isoformat()}
        for k in range(profile.n_installments)
    ]

    payers: list[dict] = []
    subscriptions: list[dict] = []
    for i in range(profile.customers):
        payer_id = f"pyr_{mch_id[-6:]}_{i:04d}"
        # A small tail is ineligible: no mandate, or cancel-anytime terms.
        # The screen exists to catch these, so a book with none is unrealistic.
        roll = rng.random()
        has_mandate = roll > 0.03
        committed = roll > 0.09
        payer = {
            "id": payer_id, "firstName": f"Customer{i:03d}",
            "emailAddress": f"c{i:03d}@example.test",
            "sources": ([{"id": f"src_{i}", "sourceType": "bank-account"}]
                        if has_mandate else []),
            "agreements": ([{"id": f"agr_{i}", "status": "active"}]
                           if has_mandate else []),
        }
        payers.append(payer)
        subscriptions.append({
            "id": f"sub_{mch_id[-6:]}_{i:04d}",
            "planId": plan_id,
            "status": "active" if committed else "cancel-anytime",
            "payer": payer,
            "payments": schedule,
        })

    return {
        "merchant_id": mch_id,
        "payers": payers,
        "plans": [{"id": plan_id, "name": f"{profile.name} {profile.cadence}",
                   "requiresTotalAmount": False}],
        "subscriptions": subscriptions,
        "processed_payments": processed,
        "transfers": [],
        "_mode": MODE_SIMULATED,
        "_history_source": "synthesised",
    }


# ---------------------------------------------------------------------------
# Live gateway
# ---------------------------------------------------------------------------

class LiveGateway:
    """Real Pinch API calls, test mode. Requires PINCH_APP_ID / PINCH_SECRET."""

    mode = MODE_LIVE

    def __init__(self, client: Any) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "LiveGateway":
        from pinch_client import PinchClient
        return cls(PinchClient.from_env(live=False))

    def create_managed_merchant(self, profile: BookProfile, *,
                                email: str) -> dict:
        m = self.client.create_managed_merchant(
            company_name=profile.name,
            company_email=email,
            bsb="000000", account_number="000000000",
            # Disbursement routes to an Upfront-controlled collections
            # account. This is the lockbox the whole model depends on
            # (docs/01-architecture.md).
            account_name=f"Upfront Collections — {profile.name}"[:64],
            contact_email=email,
            contact_first=profile.name.split(" ")[0][:32] or "Owner",
            contact_last="Owner",
        )
        m["_mode"] = self.mode
        return m

    def seed_book(self, mch_id: str, profile: BookProfile) -> dict:
        """Create payers, a plan, subscriptions, and a real payment history.

        Deliberately smaller than the simulated book: every payment is one
        HTTP call. See LIVE_SEED_PAYERS / LIVE_SEED_WEEKS.
        """
        scope = self.client.as_merchant(mch_id)
        today = date.today()
        rng = profile.rng

        payer_ids: list[tuple[str, str]] = []
        for i in range(min(LIVE_SEED_PAYERS, profile.customers)):
            roll = rng.random()
            mix = "hard" if roll < 0.08 else "soft" if roll < 0.30 else "ok"
            p = scope.create_payer(
                first_name=f"Customer{i:03d}", last_name="Test",
                email=f"c{i:03d}+{mch_id[-6:]}@mailinator.com",
                mobile="0400123456",
                # Must differ from the merchant's own disbursement account:
            # Pinch rejects a payer whose details match the merchant's,
            # because a business cannot direct-debit itself.
            bsb="000-001", account_number="123456789",
                account_name=f"Customer{i:03d} Test",
                metadata={"upfront": {"seeded": True, "mix": mix}},
            )
            payer_ids.append((p["id"], mix))

        n = 0
        for pid, mix in payer_ids:
            for wk in range(1, LIVE_SEED_WEEKS + 1):
                txn = today - timedelta(weeks=LIVE_SEED_WEEKS - wk + 1)
                desc = f"{profile.name} wk{wk}"
                if wk == 1 and mix == "soft":
                    desc += " #insufficient-funds"
                elif wk == 1 and mix == "hard":
                    desc += " #blocked-by-bank"
                scope.schedule_payment(
                    payer_id=pid, amount_c=profile.ticket_c,
                    transaction_date=txn.isoformat(), description=desc,
                    nonce=f"{mch_id}-{pid}-wk{wk}",
                    application_fee_c=50,
                )
                n += 1

        # Forward schedule: one Plan, one Subscription per payer. Both go
        # through the merchant scope so Current-Merchant cannot be omitted.
        plan = scope.create_plan(
            name=f"{profile.name} {profile.cadence}",
            amount_c=profile.ticket_c,
            interval=profile.cadence,
            n_payments=profile.n_installments,
        )
        for pid, _ in payer_ids:
            scope.create_subscription(
                plan_id=plan["id"], payer_id=pid,
                start_date=(today + timedelta(weeks=1)).isoformat())

        # Time-Travel past the overnight window so results actually post.
        future = (today + timedelta(days=3)).isoformat() + "T09:45:59Z"
        scope.at(future).get_events()

        return {"seeded": True, "mode": self.mode, "payments": n,
                "payers": len(payer_ids), "plan_id": plan.get("id")}

    def pull_book(self, mch_id: str, profile: Optional[BookProfile] = None) -> dict:
        """Pull the real book, standing in a history only if there isn't one.

        Everything structural — merchant, payers, mandates, plan,
        subscriptions, forward schedule — is whatever Pinch actually returns.
        The only thing that can be stood in is the settled payment history,
        and only when Pinch has none, because test-mode settlement runs on its
        own batch and a freshly seeded account has an empty history for days.

        A real merchant that has been trading always has its own history, so
        this branch never fires for them — which is the point: connect a real
        book and it is underwritten on real behaviour.

        `_history_source` travels with the pull and is surfaced to the client.
        Never drop it.
        """
        scope = self.client.as_merchant(mch_id)
        pull = scope.pull_book()
        pull["_mode"] = self.mode
        pull["_scope"] = scope
        pull["_history_source"] = "pinch"

        if not pull.get("processed_payments") and profile is not None:
            payer_ids = [p["id"] for p in pull.get("payers", []) if p.get("id")]
            pull["processed_payments"] = synthesise_attempts(
                mch_id, profile, payer_ids=payer_ids or None)
            pull["_history_source"] = "synthesised"
        return pull

    def create_payment_link(self, *, amount_c: int, description: str,
                            metadata: Optional[dict] = None) -> dict:
        r = self.client.create_payment_link(
            amount_c=amount_c, description=description, metadata=metadata)
        r["_mode"] = self.mode
        return r


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def build_gateway(force_simulated: bool = False) -> Any:
    """Live when credentials exist and the client imports, simulated otherwise.

    Never raises: a missing credential degrades to the simulator rather than
    breaking the app, because the simulator is honestly labelled everywhere
    it surfaces.
    """
    import os
    # Explicit override. Live onboarding is capped at LIVE_SEED_PAYERS because
    # every payment is an HTTP call, so a live book is far smaller than the
    # business's real customer count. For a walkthrough of the full-size
    # marketplace, force the simulator:
    #     UPFRONT_FORCE_SIMULATED=1
    if force_simulated or os.environ.get("UPFRONT_FORCE_SIMULATED") == "1":
        return SimulatedGateway()
    try:
        from pinch_client import credential_or_none, load_dotenv
        load_dotenv()
        if not (credential_or_none("PINCH_APP_ID")
                and credential_or_none("PINCH_SECRET")):
            return SimulatedGateway()
        return LiveGateway.from_env()
    except Exception as exc:                      # noqa: BLE001
        # Loud on stderr, because silently running simulated when the user
        # believes they configured live credentials is exactly the confusion
        # this whole module is built to prevent.
        print(f"[pinch] falling back to simulator: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return SimulatedGateway()
