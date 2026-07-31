"""
Adapter — turn live Pinch API responses into engine objects.
============================================================

`pinch_client.MerchantScope.pull_book()` returns raw Pinch JSON. The engine
(`engine/pricing_engine.py`) works on `Book`, `Attempt`, `Receivable`. This maps
one to the other, so the SAME pricing and risk code runs on mock data and on a
real connected account with no branching.

Keeping this mapping in one place is deliberate: when Pinch changes a field, one
file changes, and the guards plus tests catch drift.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from pricing_engine import Attempt, Receivable, Book   # noqa: E402


HARD = {"blocked-by-bank", "invalid-card", "invalid-account", "unsupported-card"}


def _dishonour_code(attempt: dict) -> str:
    d = attempt.get("dishonour") or {}
    return (d.get("code") or d.get("reason") or "").strip().lower()


def attempts_from_processed(processed: list[dict]) -> list[Attempt]:
    """Flatten GET /payments/processed into per-attempt records.

    A Payment can hold multiple Attempts. A later attempt settling means the
    earlier dishonour was 'cured', which the bad-debt scanner needs.
    """
    out: list[Attempt] = []
    for pmt in processed:
        attempts = pmt.get("attempts") or [pmt]
        settled = any(a.get("status") in ("approved", "settled") for a in attempts)
        for a in attempts:
            status = a.get("status", "")
            amount = int(a.get("amount", pmt.get("amount", 0)))
            if status == "dishonoured":
                out.append(Attempt(
                    amount_c=amount, status="dishonoured",
                    dishonour_code=_dishonour_code(a),
                    cured=settled,      # a sibling attempt settled
                ))
            elif status in ("approved", "settled"):
                out.append(Attempt(amount_c=amount, status="settled"))
    return out


def _amount_c(d: dict) -> int:
    """Pinch uses `amountInCents` on calculated payments and `amount`
    elsewhere. Read both rather than silently parsing one as zero — that
    mismatch emptied the forward book on the first live pull."""
    for key in ("amountInCents", "amount"):
        v = d.get(key)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    return 0


def _date_str(d: dict) -> str:
    for key in ("paymentDate", "transactionDate", "date"):
        v = d.get(key)
        if v:
            return str(v)
    return ""


def _weeks_out(date_str: str, now: datetime) -> int:
    s = (date_str or "").replace("Z", "+00:00")
    # Pinch returns 7 fractional digits; fromisoformat accepts at most 6.
    if "." in s:
        head, _, tail = s.partition(".")
        digits = "".join(c for c in tail if c.isdigit())[:6]
        rest = tail[len(digits):].lstrip("0123456789")
        s = f"{head}.{digits}{rest}" if digits else head + rest
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return 1
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (dt - now).days
    return max(1, round(delta / 7))


def mandated_payers(payers: list[dict]) -> set[str]:
    """Payer ids with a payment source or an active DDR agreement.

    Built from the hydrated payer list rather than the payer embedded in a
    subscription: the subscription's copy is the slim shape with both fields
    null, and trusting it screens out every real contract.
    """
    out: set[str] = set()
    for p in payers:
        pid = p.get("id")
        if not pid:
            continue
        if p.get("sources") or p.get("agreements"):
            out.add(pid)
    return out


def receivables_from_calculated(subscriptions: list[dict],
                                calculated_by_plan: dict[str, list[dict]],
                                payer_hard_fail: set[str],
                                now: datetime | None = None,
                                mandated: set[str] | None = None) -> list[Receivable]:
    """Build the forward schedule from calculated-payments per subscription."""
    now = now or datetime.now(timezone.utc)
    out: list[Receivable] = []
    for sub in subscriptions:
        payer = (sub.get("payer") or {})
        pid = payer.get("id") or sub.get("payerId") or "pyr_unknown"
        plan_id = sub.get("planId") or (sub.get("plan") or {}).get("id")
        status = (sub.get("status") or "").lower()
        committed = status in ("active", "scheduled")
        # A subscription's own sourceId is mandate evidence: the live
        # subscription payload does not embed the payer's sources or
        # agreements, so relying on those alone screened out every real
        # contract as "no active mandate".
        has_mandate = bool(payer.get("agreements") or payer.get("sources")
                           or sub.get("sourceId")
                           or (mandated and pid in mandated))
        sched = calculated_by_plan.get(plan_id, [])
        for pay in sched:
            amt = _amount_c(pay)
            if amt <= 0:
                continue
            out.append(Receivable(
                payer_id=pid,
                amount_c=amt,
                weeks_out=_weeks_out(_date_str(pay), now),
                has_mandate=has_mandate,
                committed_term=committed,
                payer_hard_fail=pid in payer_hard_fail,
            ))
    return out


def hard_fail_payers(processed: list[dict]) -> set[str]:
    bad = set()
    for pmt in processed:
        pid = (pmt.get("payer") or {}).get("id") or pmt.get("payerId")
        for a in (pmt.get("attempts") or [pmt]):
            if _dishonour_code(a) in HARD and pid:
                bad.add(pid)
    return bad


def book_from_pull(pull: dict, *, name: str, sector: str,
                   asset_class: str = "contract",
                   business_pd_annual: float = 0.045,
                   start_date: str | None = None,
                   scope=None) -> Book:
    """Assemble an engine Book from a MerchantScope.pull_book() result.

    If `scope` is given, calculated-payments are fetched per plan; otherwise the
    subscriptions' own embedded schedules are used if present.
    """
    processed = pull.get("processed_payments", [])
    subs = pull.get("subscriptions", [])
    plans = pull.get("plans", [])

    hard = hard_fail_payers(processed)

    calc: dict[str, list[dict]] = {}
    if scope is not None and start_date:
        for plan in plans:
            pid = plan.get("id")
            if not pid:
                continue
            try:
                resp = scope.calculated_payments(pid, start_date)
                calc[pid] = resp.get("payments", resp) if isinstance(resp, dict) else resp
            except Exception:
                calc[pid] = []
    else:
        for sub in subs:
            pid = sub.get("planId") or (sub.get("plan") or {}).get("id")
            if pid and "payments" in sub:
                calc[pid] = sub["payments"]

    receivables = receivables_from_calculated(
        subs, calc, hard, mandated=mandated_payers(pull.get("payers", [])))
    attempts = attempts_from_processed(processed)

    return Book(
        name=name, sector=sector, asset_class=asset_class,
        attempts=attempts, receivables=receivables,
        trading_months=24, business_pd_annual=business_pd_annual,
    )


def evaluate_connected_merchant(scope, *, name: str, sector: str,
                                asset_class: str = "contract",
                                start_date: str | None = None) -> dict:
    """End-to-end: pull a live book and price it with the engine."""
    from pricing_engine import price_deal
    pull = scope.pull_book()
    book = book_from_pull(pull, name=name, sector=sector,
                          asset_class=asset_class, start_date=start_date,
                          scope=scope)
    return {"book": book, "pull": pull, "pricing": price_deal(book)}
