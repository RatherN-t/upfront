"""
Mock book generator — produces Pinch-shaped data for the demo.

Each business is a *managed merchant* under Upfront's master account.
The attempt history is what you'd get from GET /payments/processed (paged),
and the receivables are what you'd get from
GET /subscriptions + GET /plans/{id}/calculated-payments (contracts)
or your invoice table (B2B invoices).
"""

import random
from pricing_engine import Attempt, Receivable, Book

random.seed(1729)   # deterministic — the demo must be identical every run


def make_attempts(n, gross_dishonour, cure_rate, hard_share, avg_amount_c, spread=0.35):
    """Synthesise a 24-month payment history with a realistic failure mix.

    `cure_rate` is the OVERALL share of dishonoured value that is later
    recovered on retry. Hard failures never cure, so the per-soft-failure
    cure probability is grossed up accordingly.
    """
    cure_within_soft = min(0.99, cure_rate / max(1e-9, 1 - hard_share))
    out = []
    for _ in range(n):
        amt = max(500, int(random.gauss(avg_amount_c, avg_amount_c * spread)))
        if random.random() < gross_dishonour:
            if random.random() < hard_share:
                code = random.choice(["blocked-by-bank", "invalid-account", "invalid-card"])
                cured = False
            else:
                code = random.choice(["insufficient-funds", "insufficient-funds",
                                      "temporary-problem"])
                cured = random.random() < cure_within_soft
            out.append(Attempt(amt, "dishonoured", code, cured))
        else:
            out.append(Attempt(amt, "settled"))
    return out


def contract_receivables(n_contracts, weeks, weekly_c, n_payers,
                         n_cancel_anytime=0, n_no_mandate=0, n_hard_fail=0,
                         concentrated_payer_share=0.0):
    """Committed weekly subscription instalments."""
    rs = []
    payers = [f"pyr_{i:04d}" for i in range(n_payers)]
    for c in range(n_contracts):
        pid = payers[c % n_payers]
        if concentrated_payer_share and c < int(n_contracts * concentrated_payer_share):
            pid = "pyr_0000"          # deliberately concentrated
        for w in range(1, weeks + 1):
            rs.append(Receivable(pid, weekly_c, w, True, True))
    # ineligible tail
    for c in range(n_cancel_anytime):
        for w in range(1, weeks + 1):
            rs.append(Receivable(f"pyr_ca_{c}", weekly_c, w, True, False))
    for c in range(n_no_mandate):
        for w in range(1, weeks + 1):
            rs.append(Receivable(f"pyr_nm_{c}", weekly_c, w, False, True))
    for c in range(n_hard_fail):
        for w in range(1, weeks + 1):
            rs.append(Receivable(f"pyr_hf_{c}", weekly_c, w, True, True,
                                 payer_hard_fail=True))
    return rs


def invoice_receivables(specs):
    """specs = [(payer_id, amount_c, weeks_out, disputed, days_past_due), ...]"""
    return [Receivable(p, a, w, True, True, disputed=dsp, days_past_due=dpd)
            for p, a, w, dsp, dpd in specs]


# ---------------------------------------------------------------------------
# BOOK 1 — Voltride (the hero demo). E-bike subscription rentals.
#   184 committed contracts x 26 weekly payments of $34.78
#   Clean history, low concentration -> Grade A / A-
# ---------------------------------------------------------------------------
voltride = Book(
    name="Voltride",
    sector="E-bike subscription rentals",
    asset_class="contract",
    trading_months=31,
    business_pd_annual=0.045,
    attempts=make_attempts(n=4820, gross_dishonour=0.066, cure_rate=0.680,
                           hard_share=0.22, avg_amount_c=3478),
    receivables=contract_receivables(n_contracts=184, weeks=26, weekly_c=3478,
                                     n_payers=184,
                                     n_cancel_anytime=12, n_no_mandate=4),
)

# ---------------------------------------------------------------------------
# BOOK 2 — Northline Gyms. Longer contracts, cleanest history -> Grade A
# ---------------------------------------------------------------------------
northline = Book(
    name="Northline Gyms",
    sector="Fitness memberships",
    asset_class="contract",
    trading_months=48,
    business_pd_annual=0.035,
    attempts=make_attempts(n=9100, gross_dishonour=0.048, cure_rate=0.72,
                           hard_share=0.18, avg_amount_c=1595),
    receivables=contract_receivables(n_contracts=310, weeks=26, weekly_c=1595,
                                     n_payers=310,
                                     n_cancel_anytime=41, n_no_mandate=9),
)

# ---------------------------------------------------------------------------
# BOOK 3 — Studio 04. Young tutoring business, messier book -> Grade B/B+
# ---------------------------------------------------------------------------
studio04 = Book(
    name="Studio 04",
    sector="After-school tutoring",
    asset_class="contract",
    trading_months=14,
    business_pd_annual=0.090,
    attempts=make_attempts(n=1640, gross_dishonour=0.104, cure_rate=0.55,
                           hard_share=0.31, avg_amount_c=6500),
    receivables=contract_receivables(n_contracts=96, weeks=20, weekly_c=6500,
                                     n_payers=88,
                                     n_cancel_anytime=14, n_no_mandate=6,
                                     n_hard_fail=5,
                                     concentrated_payer_share=0.14),
)

# ---------------------------------------------------------------------------
# BOOK 4 — Kerrigan Fitout. B2B INVOICE factoring (second asset class).
#   Lumpy, concentrated, longer-dated, no direct-debit mandate history.
#   This one demonstrates *why* invoices price wider than mandated contracts.
# ---------------------------------------------------------------------------
kerrigan = Book(
    name="Kerrigan Fitout",
    sector="Commercial fitout (B2B)",
    asset_class="invoice",
    trading_months=19,
    business_pd_annual=0.075,
    attempts=make_attempts(n=310, gross_dishonour=0.118, cure_rate=0.45,
                           hard_share=0.28, avg_amount_c=1_450_000),
    receivables=invoice_receivables([
        ("dbt_bluestone", 4_200_000,  4, False, 0),
        ("dbt_bluestone", 3_100_000,  7, False, 0),
        ("dbt_harbourco", 2_650_000,  5, False, 0),
        ("dbt_harbourco", 1_900_000,  9, False, 0),
        ("dbt_meridian",  2_300_000,  6, False, 0),
        ("dbt_meridian",  1_150_000, 11, False, 0),
        ("dbt_ovalgroup", 1_800_000,  8, False, 0),
        ("dbt_pinnacle",    950_000,  3, False, 0),
        ("dbt_pinnacle",    720_000, 13, False, 0),
        ("dbt_wren",        640_000,  2, True,  0),    # disputed -> excluded
        ("dbt_stale",       880_000,  1, False, 118),  # 90+ dpd -> excluded
    ]),
)

ALL_BOOKS = [voltride, northline, studio04, kerrigan]
