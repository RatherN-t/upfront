"""
Collections engine tests — no network, no real Pinch call.

Fakes stand in for MerchantScope / PinchClient and record what they were
asked to do, so tests assert on the SHAPE of the call (which headers implied,
which nonce, which merchant) rather than on any live response.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collections_engine import (  # noqa: E402
    Decision, IllegalTransition, MAX_RETRIES, Week, WeekState,
    classify, fire_recourse, handle_event, process_week, retry_payment,
)
from pinch_client import WebhookVerificationError  # noqa: E402


# ---------------------------------------------------------------------------
# fakes

class FakeScope:
    """Records every schedule_payment call. Never touches the network."""

    def __init__(self):
        self.calls: list[dict] = []

    def schedule_payment(self, *, payer_id, amount_c, transaction_date,
                         description="", nonce=None, application_fee_c=None,
                         source_id=None):
        call = dict(payer_id=payer_id, amount_c=amount_c,
                   transaction_date=transaction_date, description=description,
                   nonce=nonce, application_fee_c=application_fee_c)
        self.calls.append(call)
        return {"id": "pmt_fake", "nonce": nonce, "status": "scheduled"}


class FakeMasterClient:
    """Stands in for the base PinchClient. Records whether `merchant` was
    ever passed — recourse must never pass it."""

    def __init__(self):
        self.calls: list[dict] = []

    def _request(self, method, path, *, body=None, query=None,
                merchant=None, time_travel=None):
        self.calls.append(dict(method=method, path=path, body=body,
                              merchant=merchant, time_travel=time_travel))
        return {"id": "pmt_recourse", "status": "scheduled"}


# ---------------------------------------------------------------------------

class TestClassify(unittest.TestCase):
    def test_soft_codes_retry(self):
        for code in ("insufficient-funds", "temporary-problem", "technical-error"):
            self.assertEqual(classify(code), "soft")

    def test_hard_codes_never_retry(self):
        for code in ("blocked-by-bank", "invalid-card", "invalid-account",
                    "unsupported-card"):
            self.assertEqual(classify(code), "hard")

    def test_unknown_code_is_not_soft(self):
        """The whole point of the split: an unseen code must not be treated
        as retryable, or a hard-shaped failure sneaks through and burns
        decline fees for nothing."""
        self.assertEqual(classify("some-new-code-pinch-invented"), "unknown")
        self.assertNotEqual(classify("some-new-code-pinch-invented"), "soft")

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(classify("  Insufficient-Funds  "), "soft")


class TestWeekStateMachine(unittest.TestCase):
    def test_settled_can_reverse_to_dishonoured(self):
        """A payment can settle and then reverse days later when bank results
        post — this must be a legal transition, not an exception."""
        w = Week(payment_id="pmt_1", state=WeekState.SETTLED)
        w.transition(WeekState.DISHONOURED_SOFT)
        self.assertEqual(w.state, WeekState.DISHONOURED_SOFT)

    def test_scheduled_cannot_jump_to_settled(self):
        """A week must go through processing; skipping it is not a real
        sequence of Pinch events and must not be representable as legal."""
        w = Week(payment_id="pmt_1", state=WeekState.SCHEDULED)
        with self.assertRaises(IllegalTransition):
            w.transition(WeekState.SETTLED)

    def test_written_off_is_absorbing(self):
        w = Week(payment_id="pmt_1", state=WeekState.WRITTEN_OFF)
        with self.assertRaises(IllegalTransition):
            w.transition(WeekState.RETRYING)

    def test_recourse_fired_is_absorbing(self):
        w = Week(payment_id="pmt_1", state=WeekState.RECOURSE_FIRED)
        with self.assertRaises(IllegalTransition):
            w.transition(WeekState.DISHONOURED_HARD)


class TestRetryPayment(unittest.TestCase):
    def test_soft_failure_reschedules_through_scope(self):
        scope = FakeScope()
        retry_payment(scope, payer_id="pyr_1", amount_c=3478,
                     transaction_date="2026-08-05",
                     original_payment_id="pmt_orig", attempt_no=1)
        self.assertEqual(len(scope.calls), 1)
        self.assertEqual(scope.calls[0]["payer_id"], "pyr_1")
        self.assertEqual(scope.calls[0]["amount_c"], 3478)

    def test_same_logical_retry_twice_is_the_same_nonce(self):
        """A retry that times out and gets re-sent must not double-charge —
        the resend has to land on the identical nonce Pinch already saw."""
        scope = FakeScope()
        retry_payment(scope, payer_id="pyr_1", amount_c=3478,
                     transaction_date="2026-08-05",
                     original_payment_id="pmt_orig", attempt_no=1)
        retry_payment(scope, payer_id="pyr_1", amount_c=3478,
                     transaction_date="2026-08-05",
                     original_payment_id="pmt_orig", attempt_no=1)
        n1, n2 = scope.calls[0]["nonce"], scope.calls[1]["nonce"]
        self.assertEqual(n1, n2)
        self.assertTrue(n1)

    def test_different_attempt_no_gets_different_nonce(self):
        scope = FakeScope()
        retry_payment(scope, payer_id="pyr_1", amount_c=3478,
                     transaction_date="2026-08-05",
                     original_payment_id="pmt_orig", attempt_no=1)
        retry_payment(scope, payer_id="pyr_1", amount_c=3478,
                     transaction_date="2026-08-12",
                     original_payment_id="pmt_orig", attempt_no=2)
        self.assertNotEqual(scope.calls[0]["nonce"], scope.calls[1]["nonce"])

    def test_retry_cap_is_enforced(self):
        scope = FakeScope()
        with self.assertRaises(ValueError):
            retry_payment(scope, payer_id="pyr_1", amount_c=3478,
                         transaction_date="2026-08-19",
                         original_payment_id="pmt_orig",
                         attempt_no=MAX_RETRIES + 1)
        self.assertEqual(scope.calls, [])  # refused before any call went out


class TestFireRecourse(unittest.TestCase):
    def test_recourse_goes_to_master_without_current_merchant(self):
        master = FakeMasterClient()
        fire_recourse(master, recourse_payer_id="pyr_business",
                     amount_c=10000, transaction_date="2026-08-05",
                     deal_id="dl_2026_voltride", reason="hard dishonour")
        self.assertEqual(len(master.calls), 1)
        call = master.calls[0]
        self.assertIsNone(call["merchant"])  # the whole point of D3
        self.assertEqual(call["path"], "/payments")
        self.assertEqual(call["body"]["payerId"], "pyr_business")
        self.assertEqual(call["body"]["amount"], 10000)
        self.assertTrue(call["body"]["nonce"])

    def test_recourse_nonce_is_deterministic(self):
        master = FakeMasterClient()
        fire_recourse(master, recourse_payer_id="pyr_business",
                     amount_c=10000, transaction_date="2026-08-05",
                     deal_id="dl_1", reason="hard dishonour")
        fire_recourse(master, recourse_payer_id="pyr_business",
                     amount_c=10000, transaction_date="2026-08-05",
                     deal_id="dl_1", reason="hard dishonour")
        n1 = master.calls[0]["body"]["nonce"]
        n2 = master.calls[1]["body"]["nonce"]
        self.assertEqual(n1, n2)


class TestProcessWeek(unittest.TestCase):
    def _processing_week(self):
        w = Week(payment_id="pmt_1")
        process_week(w, outcome="processing")
        return w

    def test_soft_dishonour_retries(self):
        w = self._processing_week()
        d = process_week(w, outcome="dishonoured",
                         dishonour_code="insufficient-funds")
        self.assertEqual(d.action, "retry")
        self.assertEqual(d.next_state, WeekState.RETRYING)

    def test_hard_dishonour_goes_straight_to_recourse(self):
        w = self._processing_week()
        d = process_week(w, outcome="dishonoured",
                         dishonour_code="blocked-by-bank")
        self.assertEqual(d.action, "recourse")
        self.assertEqual(d.next_state, WeekState.RECOURSE_FIRED)

    def test_unknown_dishonour_goes_to_recourse_not_retry(self):
        w = self._processing_week()
        d = process_week(w, outcome="dishonoured",
                         dishonour_code="a-code-that-does-not-exist-yet")
        self.assertEqual(d.action, "recourse")

    def test_repeated_soft_failures_exhaust_the_cap_then_recourse(self):
        w = self._processing_week()
        for _ in range(MAX_RETRIES):
            d = process_week(w, outcome="dishonoured",
                            dishonour_code="insufficient-funds")
            self.assertEqual(d.action, "retry")
            # bank result comes back for the retry too
            process_week(w, outcome="processing")
        d = process_week(w, outcome="dishonoured",
                        dishonour_code="insufficient-funds")
        self.assertEqual(d.action, "recourse")

    def test_settled_then_reversed_is_handled(self):
        w = self._processing_week()
        process_week(w, outcome="settled")
        self.assertEqual(w.state, WeekState.SETTLED)
        d = process_week(w, outcome="dishonoured",
                         dishonour_code="blocked-by-bank")
        self.assertEqual(d.next_state, WeekState.RECOURSE_FIRED)


# ---------------------------------------------------------------------------
# webhook handling

SECRET = "shhh123"  # short fixture, no sk_/whsec_ prefix — not a real credential


def _sign(secret: str, raw_body: bytes, ts: int | None = None) -> str:
    ts = ts if ts is not None else int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + raw_body,
                   hashlib.sha256).hexdigest()
    return f"t={ts},v2={sig}"


class TestHandleEvent(unittest.TestCase):
    def test_valid_event_is_returned(self):
        body = json.dumps({"id": "evt_1", "type": "bank-results"}).encode()
        header = _sign(SECRET, body)
        seen = set()
        event = handle_event(body, header, SECRET, seen)
        self.assertEqual(event["id"], "evt_1")
        self.assertIn("evt_1", seen)

    def test_duplicate_event_id_is_ignored_on_second_delivery(self):
        body = json.dumps({"id": "evt_dupe", "type": "transfer"}).encode()
        header = _sign(SECRET, body)
        seen = set()
        first = handle_event(body, header, SECRET, seen)
        second = handle_event(body, header, SECRET, seen)
        self.assertIsNotNone(first)
        self.assertIsNone(second)  # no second retry/recourse fired

    def test_bad_signature_raises_before_any_parsing(self):
        # body is deliberately unparseable JSON — if verification ran after
        # parsing, this would fail with a JSON error instead of a signature
        # error, proving the ordering was wrong
        body = b"{not valid json"
        header = _sign(SECRET, b"different body entirely")
        seen = set()
        with self.assertRaises(WebhookVerificationError):
            handle_event(body, header, SECRET, seen)
        self.assertEqual(seen, set())  # no side effect from the rejected event

    def test_wrong_secret_raises(self):
        body = json.dumps({"id": "evt_2"}).encode()
        header = _sign("a-different-secret", body)
        with self.assertRaises(WebhookVerificationError):
            handle_event(body, header, SECRET, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestRecourseMoneyType(unittest.TestCase):
    """fire_recourse bypasses schedule_payment, so it bypasses the client's
    own float check. It must reject float money itself."""

    def test_float_amount_rejected_before_any_call(self):
        class Recorder:
            calls = []

            def _request(self, *a, **k):
                self.calls.append((a, k))
                return {}

        rec = Recorder()
        with self.assertRaises(TypeError):
            fire_recourse(rec, recourse_payer_id="pyr_1", amount_c=100.0,
                          transaction_date="2026-08-05", deal_id="dl_1",
                          reason="hard-fail")
        self.assertEqual(rec.calls, [],
                         "no request may go out once the amount is rejected")

    def test_bool_amount_rejected(self):
        class Recorder:
            def _request(self, *a, **k):
                raise AssertionError("must not be called")

        with self.assertRaises(TypeError):
            fire_recourse(Recorder(), recourse_payer_id="pyr_1", amount_c=True,
                          transaction_date="2026-08-05", deal_id="dl_1",
                          reason="hard-fail")
