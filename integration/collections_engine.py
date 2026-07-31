"""
Collections engine — retry vs recourse, made a state machine.
==============================================================

Upfront collects the revenue it advanced against, on the Pinch rail, itself.
The whole "repayment is plumbing, not a promise" claim reduces to one decision,
made over and over: a scheduled week fails, and something has to decide whether
to try again or to fall back to the business's own recourse mandate.

Two things make this file exist rather than a boolean flag on Payment:

  * Soft failures (insufficient-funds, temporary-problem, technical-error) are
    worth a fresh attempt. Hard failures (blocked-by-bank, invalid-card,
    invalid-account, unsupported-card) are not — each retry burns a $5 decline
    fee (engine/fees.py DECLINE_FEE_C) and cannot succeed by construction.
    Getting this split wrong either abandons collectable money or throws it
    away on fees.

  * `settled` is not terminal. A direct debit clears the overnight batch, then
    the bank can still reverse it days later (docs/02-pinch-integration.md
    §6). A boolean "did it pay" can't represent that; a state machine can, and
    can reject the transitions that must never happen (e.g. resurrecting a
    written-off week, or retrying past the cap).

Everything that moves money here carries a nonce derived from stable inputs
(original payment id + attempt number, or deal id + reason + date), so a
timed-out request that gets re-sent lands on the same nonce and Pinch's
nonce-replay behaviour (HTTP 403 with the existing `pmt_` body, which
`pinch_client` already treats as success) absorbs it instead of a second
debit going out.

Named `collections_engine`, not `collections`: the stdlib module of that name
is already in `sys.modules` by the time any test runner or script starts
(`dataclasses`/`enum`/`unittest` pull it in first), so `import collections`
anywhere in this process resolves to the stdlib package regardless of
sys.path — a local `collections.py` here would be permanently unimportable
by its own name, not just shadowed.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pinch_client import (  # noqa: E402
    MerchantScope, PinchClient, WebhookVerificationError, _cents,
    verify_webhook)


# ---------------------------------------------------------------------------
# 1. classify — the whole retry/never-retry split in one place

SOFT_CODES = {"insufficient-funds", "temporary-problem", "technical-error"}
HARD_CODES = {"blocked-by-bank", "invalid-card", "invalid-account", "unsupported-card"}

MAX_RETRIES = 2  # third soft failure goes to recourse, not a third decline fee


def classify(dishonour_code: str) -> str:
    """"soft" (retry), "hard" (never retry), or "unknown".

    Unknown is deliberately NOT soft. Pinch's dishonour vocabulary is the
    documented eight codes; a code this project has not seen before is more
    likely a new hard failure than a new soft one, and retrying a hard code
    burns a real $5 decline fee for a payment that cannot succeed. Treat the
    unseen case as if it were hard until someone has looked at it.
    """
    code = (dishonour_code or "").strip().lower()
    if code in SOFT_CODES:
        return "soft"
    if code in HARD_CODES:
        return "hard"
    return "unknown"


# ---------------------------------------------------------------------------
# 2. WeekState — one scheduled week, as a state machine

class WeekState(Enum):
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SETTLED = "settled"
    DISHONOURED_SOFT = "dishonoured_soft"
    DISHONOURED_HARD = "dishonoured_hard"
    RETRYING = "retrying"
    RECOURSE_FIRED = "recourse_fired"
    WRITTEN_OFF = "written_off"


# Legal transitions only. SETTLED -> DISHONOURED_* is the reversal case
# (docs/02-pinch-integration.md §6): a bank-results batch can post a clean
# settlement and days later post a reversal against the same payment.
# WRITTEN_OFF and RECOURSE_FIRED are absorbing — there is nothing to retry
# once recourse has fired or the week has been given up on.
_TRANSITIONS: dict[WeekState, set[WeekState]] = {
    WeekState.SCHEDULED: {WeekState.PROCESSING, WeekState.WRITTEN_OFF},
    WeekState.PROCESSING: {WeekState.SETTLED, WeekState.DISHONOURED_SOFT,
                           WeekState.DISHONOURED_HARD},
    WeekState.SETTLED: {WeekState.DISHONOURED_SOFT, WeekState.DISHONOURED_HARD},
    WeekState.DISHONOURED_SOFT: {WeekState.RETRYING, WeekState.RECOURSE_FIRED,
                                 WeekState.WRITTEN_OFF},
    WeekState.DISHONOURED_HARD: {WeekState.RECOURSE_FIRED, WeekState.WRITTEN_OFF},
    # RETRYING means "a retry payment has been fired, awaiting its own bank
    # result" — it goes back through PROCESSING like any fresh payment before
    # landing on SETTLED or a fresh dishonour.
    WeekState.RETRYING: {WeekState.PROCESSING, WeekState.SETTLED,
                         WeekState.DISHONOURED_SOFT, WeekState.DISHONOURED_HARD},
    WeekState.RECOURSE_FIRED: set(),
    WeekState.WRITTEN_OFF: set(),
}


class IllegalTransition(ValueError):
    pass


@dataclass
class Week:
    """One scheduled payment's state, plus the bookkeeping a decision needs.

    `attempt_no` counts payment attempts against the payer (starts at 1, the
    original schedule); `retries_used` counts how many of those were retries
    fired by this module, which is what the cap in `retry_payment` checks.
    """
    payment_id: str
    state: WeekState = WeekState.SCHEDULED
    attempt_no: int = 1
    retries_used: int = 0

    def transition(self, new_state: WeekState) -> WeekState:
        """Apply a transition and return the resulting state (for chaining
        into a Decision), or raise IllegalTransition and leave state as-is."""
        allowed = _TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise IllegalTransition(
                f"{self.payment_id}: {self.state.value} -> {new_state.value} "
                f"is not a legal transition (allowed: "
                f"{sorted(s.value for s in allowed)})")
        self.state = new_state
        return self.state


# ---------------------------------------------------------------------------
# 3. retry_payment — reschedule a soft failure, deterministically

def _retry_nonce(original_payment_id: str, attempt_no: int) -> str:
    """Same (payment, attempt) always produces the same nonce.

    Derived, not random: a caller that times out mid-request and re-sends the
    identical retry_payment() call must reproduce this exact nonce, so Pinch's
    nonce-replay path (existing payment returned, not a new one) absorbs the
    resend instead of it becoming a second debit. Hashed rather than
    concatenated raw so a payment id containing "-" can't collide with the
    attempt-number separator.
    """
    raw = f"retry:{original_payment_id}:{attempt_no}".encode()
    return "retry_" + hashlib.sha256(raw).hexdigest()[:24]


def retry_payment(scope: MerchantScope, *, payer_id: str, amount_c: int,
                  transaction_date: str, original_payment_id: str,
                  attempt_no: int, application_fee_c: Optional[int] = None) -> dict:
    """Reschedule a soft-failed payment. Refuses beyond MAX_RETRIES.

    `attempt_no` is the retry count for THIS payment (1 = first retry, 2 =
    second, ...), not the cumulative attempt number on the payer. Capping here
    rather than upstream keeps the decline-fee ceiling enforced at the one
    place money actually goes out.
    """
    if attempt_no > MAX_RETRIES:
        raise ValueError(
            f"{original_payment_id}: attempt {attempt_no} exceeds "
            f"MAX_RETRIES={MAX_RETRIES} — fall back to recourse instead")
    nonce = _retry_nonce(original_payment_id, attempt_no)
    return scope.schedule_payment(
        payer_id=payer_id, amount_c=amount_c,
        transaction_date=transaction_date,
        description=f"retry {attempt_no}/{MAX_RETRIES} of {original_payment_id}",
        nonce=nonce, application_fee_c=application_fee_c,
    )


# ---------------------------------------------------------------------------
# 4. fire_recourse — debit the BUSINESS, on Upfront's OWN account

def fire_recourse(master_client: PinchClient, *, recourse_payer_id: str,
                  amount_c: int, transaction_date: str, deal_id: str,
                  reason: str) -> dict:
    """Direct-debit the business's own recourse mandate (docs/00-decisions.md
    D3) after collection from the end customer has failed.

    This is the ONE deliberate exception to "every merchant call goes through
    as_merchant()". Recourse is not against the managed merchant's customer —
    it is against the BUSINESS itself, which is a Payer of Upfront's own
    master merchant account. Sending `Current-Merchant` here would misroute
    the debit onto the financed business's own Pinch account instead of
    Upfront's, defeating the point of recourse entirely. So this calls
    `master_client` — the bare `PinchClient`, not a `MerchantScope` — and that
    is correct, not an oversight. Everywhere else in this codebase is built so
    that omitting `as_merchant()` is impossible; this is the one call it must
    stay impossible to accidentally route the other way, which is why it
    takes a `PinchClient` and not a scope in its signature.
    """
    # This bypasses `schedule_payment`, so it also bypasses the `_cents()`
    # check that normally rejects float money at the API boundary. Apply it
    # here rather than trusting the caller — this is the one money-moving
    # call in the codebase with no other guard in front of it.
    amount_c = _cents(amount_c)

    nonce = "recourse_" + hashlib.sha256(
        f"recourse:{deal_id}:{reason}:{transaction_date}".encode()
    ).hexdigest()[:24]
    return master_client._request(
        "POST", "/payments", body={
            "payerId": recourse_payer_id,
            "amount": amount_c,
            "transactionDate": transaction_date,
            "description": f"recourse {deal_id}: {reason}",
            "nonce": [nonce],
        },
    )


# ---------------------------------------------------------------------------
# 5. process_week — pure decision logic

@dataclass
class Decision:
    next_state: WeekState
    action: str  # "retry" | "recourse" | "write_off" | "none"


def process_week(week: Week, *, outcome: str, dishonour_code: str = "") -> Decision:
    """Given a week's current state and an observed outcome, decide the next
    state and what to do about it. No I/O — callers use the result to drive
    retry_payment / fire_recourse. `outcome` is one of "processing", "settled",
    "dishonoured".
    """
    if outcome == "processing":
        return Decision(week.transition(WeekState.PROCESSING), "none")

    if outcome == "settled":
        return Decision(week.transition(WeekState.SETTLED), "none")

    if outcome != "dishonoured":
        raise ValueError(f"unknown outcome {outcome!r}")

    kind = classify(dishonour_code)
    if kind == "soft":
        week.transition(WeekState.DISHONOURED_SOFT)
        if week.retries_used < MAX_RETRIES:
            week.retries_used += 1
            return Decision(week.transition(WeekState.RETRYING), "retry")
        # cap reached: same failure keeps happening, stop paying decline fees
        return Decision(week.transition(WeekState.RECOURSE_FIRED), "recourse")

    # hard and unknown are both never-retry (see classify()) — go straight
    # to recourse rather than burn a decline fee on a payment that can't clear
    week.transition(WeekState.DISHONOURED_HARD)
    return Decision(week.transition(WeekState.RECOURSE_FIRED), "recourse")


# Guards the check-and-insert in handle_event. See its docstring for why a
# plain `if id in seen: seen.add(id)` is not safe under concurrent delivery.
_dedupe_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 6. handle_event — webhook entrypoint: verify, then dedupe, then act

def handle_event(raw_body: bytes, signature_header: str, secret: str,
                 seen_event_ids: set) -> Optional[dict]:
    """Verify signature on the RAW bytes, THEN parse. Never the other order —
    re-serialising JSON before verifying changes whitespace/key order and a
    genuine delivery stops verifying (see pinch_client.verify_webhook).

    Dedupes on `evt_` id: events arrive more than once
    (docs/02-pinch-integration.md §6), and processing the same bank-results or
    transfer event twice must not fire a second retry or recourse debit.
    Returns None for a duplicate; the caller then does nothing rather than
    replay side effects.

    `seen_event_ids` is mutated in place (id added on first sight) so the
    caller's dedupe store persists across calls without this function owning
    storage.

    The membership test and the insert are done under a lock. Pinch delivers
    concurrently and retries on timeout, so two threads can hold the same
    `evt_` at once; testing and then inserting as two separate statements
    lets both pass the test before either inserts, and both go on to fire a
    retry or a recourse debit. The GIL does not help — it can switch between
    the two statements.

    A single process-wide lock is enough here and deliberately coarse: this
    guards a set membership check, not I/O. **A multi-process deployment
    needs a unique constraint on the event id in the database instead** — a
    lock in one process says nothing about another.
    """
    verify_webhook(secret, signature_header, raw_body)  # raises on bad signature

    event = json.loads(raw_body.decode())

    event_id = event.get("id", "")
    if not event_id.startswith("evt_"):
        raise ValueError(f"event missing evt_ id: {event!r}")

    with _dedupe_lock:
        if event_id in seen_event_ids:
            return None
        seen_event_ids.add(event_id)
    return event
