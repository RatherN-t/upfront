"""
Upfront — pricing & risk engine (v2, "honest")
==============================================

v1 produced a 14.25% investor net yield. That number was wrong. This file
documents why, and computes the number that survives scrutiny.

WHAT v1 GOT WRONG
-----------------
1. It ignored Pinch processing fees entirely. On a $34.78 weekly debit those
   cost 2.85% of collections; on an $11.50 gym debit, 5.80%. The v1 gross
   discount was 4.58%. Fees were therefore eating most of the margin and were
   simply absent from the model.

2. It treated subscription revenue as a RECEIVABLE. It isn't. An invoice is
   money owed for work already delivered; the debtor owes it whether or not the
   supplier survives. A subscription is money owed for a service not yet
   delivered. If the business fails, the service stops and the stream stops
   with it. v1's loss model assumed the stream keeps collecting after business
   failure. It does not.

3. It used a business default probability of ~1% p.a. Prospa, Australia's
   largest listed SME lender, realised NET bad debt of 5.7% (FY22) and 9.9%
   (FY23) on its book while charging around 35% APR. Businesses that seek
   receivables finance are adversely selected for cash-flow stress. 1% is not
   a defensible input.

4. It ignored cash drag. An investor's capital is only earning while deployed.

5. It never checked whether the platform's own 25% share could actually fund a
   licensed, compliant operating business.

The corrected engine models all five. All money in CENTS.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from fees import profile_for_book, dd_fee_c, DECLINE_FEE_C, TRANSFER_FEE_C


# ---------------------------------------------------------------------------
# IRR / WAL
# ---------------------------------------------------------------------------

def npv(rate: float, cfs: List[float]) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cfs))


def irr(cfs: List[float], periods_per_year: float,
        lo: float = -0.10, hi: float = 2.0, tol: float = 1e-10) -> float:
    """Annualised effective IRR. Scans upward for the first sign change so that
    the spurious root near -100% on amortising schedules is never returned."""
    steps, prev_r, prev_f, found = 2000, lo, npv(lo, cfs), False
    for i in range(1, steps + 1):
        r = lo + (hi - lo) * i / steps
        f = npv(r, cfs)
        if prev_f * f <= 0:
            lo, hi, found = prev_r, r, True
            break
        prev_r, prev_f = r, f
    if not found:
        return float("nan")
    for _ in range(300):
        mid = (lo + hi) / 2
        fm = npv(mid, cfs)
        if abs(fm) < tol:
            break
        if npv(lo, cfs) * fm < 0:
            hi = mid
        else:
            lo = mid
    return (1 + (lo + hi) / 2) ** periods_per_year - 1


def wal_years(cfs_after_t0: List[float], ppy: float) -> float:
    tot = sum(cfs_after_t0)
    if tot == 0:
        return 0.0
    return sum((t + 1) * cf for t, cf in enumerate(cfs_after_t0)) / tot / ppy


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

HARD_CODES = {"blocked-by-bank", "invalid-card", "invalid-account", "unsupported-card"}
SOFT_CODES = {"insufficient-funds", "temporary-problem", "technical-error"}


@dataclass
class Attempt:
    amount_c: int
    status: str
    dishonour_code: str = ""
    cured: bool = False


@dataclass
class Receivable:
    payer_id: str
    amount_c: int
    weeks_out: int
    has_mandate: bool
    committed_term: bool
    payer_hard_fail: bool = False
    disputed: bool = False
    days_past_due: int = 0


@dataclass
class Book:
    name: str
    sector: str
    asset_class: str                 # "contract" | "invoice"
    attempts: List[Attempt] = field(default_factory=list)
    receivables: List[Receivable] = field(default_factory=list)
    trading_months: int = 24
    business_pd_annual: float = 0.05  # see RiskPolicy for why this is not 1%
    method: str = "dd"


# ---------------------------------------------------------------------------
# Risk policy — every number here is an assumption you must be able to defend
# ---------------------------------------------------------------------------

@dataclass
class RiskPolicy:
    # --- what survives if the business fails mid-term ---
    # An invoice is for work already done: the debtor still owes it.
    # A subscription is for service not yet delivered: it dies with the business.
    continuation_on_failure: Dict[str, float] = field(default_factory=lambda: {
        "invoice": 0.75,
        "contract": 0.15,
    })
    # what you recover from an insolvent business under recourse, unsecured
    recourse_recovery: float = 0.20
    # PPSR-registered security over the receivables lifts this materially
    recourse_recovery_with_ppsr: float = 0.45
    use_ppsr: bool = True

    # --- adverse selection ---
    # Businesses seeking receivables finance are cash-flow stressed. The ASIC
    # base rate across all registered companies is ~0.5% p.a.; the observed
    # loss experience of Australian SME lenders is an order of magnitude higher.
    adverse_selection_multiple: float = 1.0   # applied on top of book PD

    # --- investor-level ---
    cash_drag: float = 0.18          # share of investor capital idle between deals
    platform_fee_on_yield: float = 0.15   # platform's cut of investor gross yield


@dataclass
class PricingPolicy:
    base_discount_pm: float = 0.0130
    grade_spread_pm: Dict[str, float] = field(default_factory=lambda: {
        "A": 0.0000, "A-": 0.0017, "B+": 0.0040, "B": 0.0070, "C": 0.0120,
    })
    reserve_buffer: float = 0.030
    max_advance: float = 0.95
    platform_take_of_discount: float = 0.25


CONCENTRATION_CAP = 0.20
MAX_WEEKS_OUT = 26


# ---------------------------------------------------------------------------
# 1. Bad-debt scanner
# ---------------------------------------------------------------------------

def scan_bad_debt(book: Book) -> Dict:
    total_v = sum(a.amount_c for a in book.attempts)
    dis = [a for a in book.attempts if a.status == "dishonoured"]
    dis_v = sum(a.amount_c for a in dis)
    hard_v = sum(a.amount_c for a in dis if a.dishonour_code in HARD_CODES)
    cured_v = sum(a.amount_c for a in dis if a.cured)

    gross = dis_v / total_v if total_v else 0.0
    cure = cured_v / dis_v if dis_v else 0.0

    by_payer: Dict[str, int] = {}
    for r in book.receivables:
        by_payer[r.payer_id] = by_payer.get(r.payer_id, 0) + r.amount_c
    face = sum(by_payer.values()) or 1

    tickets = [r.amount_c for r in book.receivables]
    return {
        "attempts": len(book.attempts),
        "gross_dishonour_rate": gross,
        "cure_rate": cure,
        "net_loss_rate": gross * (1 - cure),
        "hard_fail_share": hard_v / dis_v if dis_v else 0.0,
        "top_payer_concentration": max(by_payer.values()) / face,
        "distinct_payers": len(by_payer),
        "median_ticket_c": sorted(tickets)[len(tickets) // 2] if tickets else 0,
    }


# ---------------------------------------------------------------------------
# 2. Eligibility
# ---------------------------------------------------------------------------

def screen(book: Book) -> Dict:
    included, excluded = [], []
    for r in book.receivables:
        reasons = []
        if not r.has_mandate:
            reasons.append("no active mandate")
        if not r.committed_term:
            reasons.append("cancel-anytime")
        if r.payer_hard_fail:
            reasons.append("payer hard-fail history")
        if r.disputed:
            reasons.append("disputed / credit note")
        if r.weeks_out > MAX_WEEKS_OUT:
            reasons.append("beyond 26-week horizon")
        if r.days_past_due > 90:
            reasons.append("90+ days past due")
        (excluded if reasons else included).append((r, reasons))

    by_payer: Dict[str, int] = {}
    for r, _ in included:
        by_payer[r.payer_id] = by_payer.get(r.payer_id, 0) + r.amount_c
    face = sum(by_payer.values())
    haircut = sum(max(0, v - face * CONCENTRATION_CAP) for v in by_payer.values())

    return {
        "included": included, "excluded": excluded,
        "gross_face_c": sum(r.amount_c for r in book.receivables),
        "screened_face_c": face,
        "concentration_haircut_c": int(haircut),
        "eligible_face_c": int(face - haircut),
    }


def grade_from_scan(scan: Dict, book: Book, fee_drag: float) -> str:
    """Fee drag is a grading input. Two books with identical bad debt but
    different ticket sizes are NOT the same credit."""
    loss, conc = scan["net_loss_rate"], scan["top_payer_concentration"]
    s = 0
    s += 0 if loss < 0.015 else 1 if loss < 0.025 else 2 if loss < 0.04 else 3
    s += 0 if conc < 0.10 else 1 if conc < 0.20 else 2
    s += 0 if book.trading_months >= 24 else 1 if book.trading_months >= 12 else 2
    s += 0 if scan["hard_fail_share"] < 0.25 else 1
    s += 0 if fee_drag < 0.015 else 1 if fee_drag < 0.030 else 2
    return ["A", "A-", "B+", "B", "C"][min(s, 4)]


# ---------------------------------------------------------------------------
# 3. Pricing — against NET settled cash
# ---------------------------------------------------------------------------

def price_deal(book: Book,
               pp: Optional[PricingPolicy] = None,
               rp: Optional[RiskPolicy] = None) -> Dict:
    pp = pp or PricingPolicy()
    rp = rp or RiskPolicy()

    scan = scan_bad_debt(book)
    scr = screen(book)
    inc = scr["included"]
    if scr["eligible_face_c"] <= 0:
        return {"fundable": False, "reason": "no eligible receivables"}

    scale = scr["eligible_face_c"] / scr["screened_face_c"]
    horizon = max(r.weeks_out for r, _ in inc)
    sched_face = [0.0] * (horizon + 1)
    for r, _ in inc:
        sched_face[r.weeks_out] += r.amount_c * scale

    loss = scan["net_loss_rate"]
    sched_gross = [v * (1 - loss) for v in sched_face]      # after customer bad debt
    gross_c = sum(sched_gross)

    # ---- Pinch fee drag on the real ticket size and cadence ----
    n_sched = len(inc)
    fp = profile_for_book(scan["median_ticket_c"], n_sched,
                          scan["gross_dishonour_rate"], scan["cure_rate"],
                          n_transfers=horizon, method=book.method)
    fee_drag = fp.drag
    sched_net = [v * (1 - fee_drag) for v in sched_gross]   # what actually settles
    net_c = sum(sched_net)

    grade = grade_from_scan(scan, book, fee_drag)

    # ---- price against NET settled cash, not gross ----
    advance_rate = min(pp.max_advance, 1 - loss - pp.reserve_buffer)
    wal_y = wal_years(sched_net[1:], 52)
    wal_m = wal_y * 12
    rate_pm = pp.base_discount_pm + pp.grade_spread_pm[grade]
    discount_c = net_c * rate_pm * wal_m

    cash_today_c = min(net_c * advance_rate, net_c - discount_c)
    reserve_c = net_c - discount_c - cash_today_c

    biz_cf = [cash_today_c] + [-v for v in sched_net[1:]]
    biz_cf[-1] += reserve_c
    biz_irr = irr(biz_cf, 52)

    # ---- investor side ----
    inv_income_c = discount_c * (1 - pp.platform_take_of_discount)
    platform_c = discount_c * pp.platform_take_of_discount
    inv_total_c = cash_today_c + inv_income_c
    inv_weekly = [v / sum(sched_net[1:]) * inv_total_c for v in sched_net[1:]]
    inv_gross_irr = irr([-cash_today_c] + inv_weekly, 52)

    # ---- expected credit loss, done properly ----
    pd_annual = book.business_pd_annual * rp.adverse_selection_multiple
    pd_life = 1 - (1 - pd_annual) ** wal_y
    cont = rp.continuation_on_failure[book.asset_class]
    rec = rp.recourse_recovery_with_ppsr if rp.use_ppsr else rp.recourse_recovery
    # at failure, on average ~half the principal is still outstanding
    avg_outstanding = 0.5
    lgd = (1 - cont) * (1 - rec)
    exp_loss_on_principal = pd_life * avg_outstanding * lgd
    loss_drag_annual = exp_loss_on_principal / wal_y if wal_y else 0.0

    inv_net_irr = inv_gross_irr - loss_drag_annual
    inv_after_drag = inv_net_irr * (1 - rp.cash_drag)

    return {
        "fundable": True, "grade": grade, "scan": scan, "screen": scr,
        "asset_class": book.asset_class,
        "gross_face_c": scr["gross_face_c"],
        "eligible_face_c": scr["eligible_face_c"],
        "gross_collections_c": gross_c,
        "fee_drag": fee_drag,
        "fee_breakdown": fp.breakdown(),
        "net_settled_c": net_c,
        "advance_rate": advance_rate,
        "discount_rate_pm": rate_pm,
        "discount_c": discount_c,
        "discount_pct": discount_c / net_c,
        "platform_c": platform_c,
        "investor_income_c": inv_income_c,
        "cash_today_c": cash_today_c,
        "reserve_c": reserve_c,
        "wal_months": wal_m,
        "term_weeks": horizon,
        "business_irr": biz_irr,
        "investor_gross_irr": inv_gross_irr,
        "pd_annual": pd_annual,
        "pd_life": pd_life,
        "continuation": cont,
        "lgd": lgd,
        "expected_loss_on_principal": exp_loss_on_principal,
        "loss_drag_annual": loss_drag_annual,
        "investor_net_irr": inv_net_irr,
        "investor_after_cash_drag": inv_after_drag,
        "weekly_net_c": sched_net,
    }


# ---------------------------------------------------------------------------
# Platform viability — can 25% of a thin discount fund a licensed business?
# ---------------------------------------------------------------------------

def platform_viability(deals: List[Dict], deployed_c: int,
                       annual_opex_c: int = 120_000_000) -> Dict:
    """Default opex $1.2m: a small AFSL-holding fintech with a trust account,
    compliance, engineering and two-sided acquisition."""
    if not deals:
        return {}
    avg_wal_y = sum(d["wal_months"] for d in deals) / len(deals) / 12
    turns = 1 / avg_wal_y if avg_wal_y else 0
    take_rate = sum(d["platform_c"] for d in deals) / sum(d["cash_today_c"] for d in deals)
    annual_rev_c = deployed_c * take_rate * turns
    return {
        "avg_wal_years": avg_wal_y,
        "turns_per_year": turns,
        "take_rate_per_deal": take_rate,
        "annual_revenue_c": annual_rev_c,
        "annual_opex_c": annual_opex_c,
        "profit_c": annual_rev_c - annual_opex_c,
        "breakeven_deployed_c": annual_opex_c / (take_rate * turns) if take_rate else 0,
    }


def d(c: float) -> str:
    return "$" + format(round(c / 100), ",")


def p(x: float, dp: int = 2) -> str:
    return f"{x * 100:.{dp}f}%"
