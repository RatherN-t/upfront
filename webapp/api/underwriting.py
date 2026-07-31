"""
Underwriting service — gateway JSON in, priced deal out.
========================================================

The one place that composes the existing pieces:

    gateway.pull_book()  ->  adapter.book_from_pull()  ->  price_deal()
                                                       ->  portfolio_risk.simulate()

No pricing, risk or fee logic lives here. If a number looks wrong, it is wrong
in `engine/`, not in this file — that separation is what lets `tools/check.py
figures` keep the docs and the engine in agreement.

Returns are always reported as a distribution. `summarise_returns` refuses to
emit a mean without the 5th percentile and the probability of loss beside it,
because the product's entire credibility problem is that a mid-teens number
looks safe and is not. See docs/05-honest-returns.md.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_ROOT / "engine", _ROOT / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from adapter import book_from_pull            # noqa: E402
from pricing_engine import price_deal         # noqa: E402
from portfolio_risk import (                  # noqa: E402
    Position, PortfolioParams, simulate)

from pinch_gateway import BookProfile         # noqa: E402


# A single deal is one position. Investors on this platform hold one book at a
# time unless they spread themselves, so the honest single-deal distribution
# is the undiversified one — which is materially worse than the portfolio
# number, and is what the marketplace shows.
SINGLE_DEAL_SIMS = 8000


def underwrite(pull: dict, profile: BookProfile) -> dict:
    """Price a pulled book. Raises nothing — returns {"fundable": False} on a
    book the screen rejects, which the caller must surface rather than hide."""
    scope = pull.get("_scope")
    book = book_from_pull(
        pull,
        name=profile.name,
        sector=profile.sector,
        asset_class=profile.asset_class,
        business_pd_annual=profile.business_pd_annual,
        start_date=date.today().isoformat(),
        scope=scope,
    )
    book.trading_months = profile.trading_months
    pricing = price_deal(book)
    if not pricing.get("fundable"):
        return {"fundable": False,
                "reason": pricing.get("reason", "not fundable"),
                "mode": pull.get("_mode", "unknown")}

    dist = distribution_for(pricing)
    pricing["distribution"] = dist
    pricing["mode"] = pull.get("_mode", "unknown")
    return pricing


def distribution_for(pricing: dict, sims: int = SINGLE_DEAL_SIMS) -> dict:
    """Monte-Carlo outcome distribution for one deal.

    Samples are requested so the UI can plot the shape, then dropped from the
    stored result — the histogram survives, the 8,000 floats do not.
    """
    pos = Position(
        name="deal",
        principal_c=pricing["cash_today_c"],
        gross_irr=pricing["investor_gross_irr"],
        wal_years=pricing["wal_months"] / 12,
        pd_annual=pricing["pd_annual"],
        asset_class=pricing["asset_class"],
    )
    dist = simulate([pos], PortfolioParams(), n=sims, seed=7,
                    include_samples=True)
    samples = dist.pop("samples", [])
    dist["curve"] = percentile_curve(samples)
    return dist


def summarise_returns(dist: dict) -> dict:
    """Mean, downside and probability of loss, always together.

    Callers must not pluck `mean` out of this and render it alone. The API
    ships these four fields as a unit and the UI renders them as a unit.
    """
    if not dist:
        return {"mean": 0.0, "p5": 0.0, "p1": 0.0, "prob_loss": 0.0}
    return {
        "mean": dist.get("mean", 0.0),
        "p5": dist.get("p5", 0.0),
        "p1": dist.get("p1", 0.0),
        "prob_loss": dist.get("prob_negative", 0.0),
    }


def percentile_curve(samples: list[float]) -> list[dict]:
    """Return at each percentile — the honest chart for this distribution.

    A histogram is the wrong tool here. A single-deal outcome is close to a
    point mass: if the business does not fail, the return is nearly
    deterministic, so ~95% of runs land in one narrow band and a histogram is
    a single spike with an empty axis beside it. Rebinning does not fix that,
    because the information is in the tail, which is long and thin.

    A percentile curve shows both without distorting either. It reads
    directly as "this outcome or worse, this often": the flat right-hand
    section is the ordinary result, and the cliff on the left is the real
    risk. It is also the same quantity quoted in the summary — p5 and p1 are
    just points on this line — so the chart and the headline numbers cannot
    drift apart.
    """
    if not samples:
        return []
    ordered = sorted(samples)
    n = len(ordered)
    out = []
    for p in range(1, 100):
        out.append({"p": p, "value": ordered[min(n - 1, int(p / 100 * n))]})
    return out


def deal_fields(pricing: dict) -> dict:
    """Flatten a priced deal into the columns `db.create_deal` expects."""
    r = summarise_returns(pricing.get("distribution", {}))
    return {
        "rail_score": pricing["grade"],
        "asset_class": pricing["asset_class"],
        "eligible_face_c": int(pricing["eligible_face_c"]),
        "net_settled_c": int(pricing["net_settled_c"]),
        "cash_today_c": int(pricing["cash_today_c"]),
        "fee_drag": float(pricing["fee_drag"]),
        "mean_return": r["mean"],
        "p5_return": r["p5"],
        "p1_return": r["p1"],
        "prob_loss": r["prob_loss"],
        "wal_months": float(pricing["wal_months"]),
        "term_weeks": int(pricing["term_weeks"]),
    }


def public_pricing(pricing: dict) -> dict:
    """The subset of a priced deal that is safe and useful to send to a client.

    Excludes the raw book and the engine's internal schedules; includes the
    fee-drag breakdown because it is the most novel thing the engine computes
    and the reason two identical-revenue books price differently.
    """
    if not pricing.get("fundable"):
        return {"fundable": False, "reason": pricing.get("reason", "")}
    scan = pricing["scan"]
    return {
        "fundable": True,
        "mode": pricing.get("mode", "unknown"),
        "rail_score": pricing["grade"],
        "asset_class": pricing["asset_class"],
        "scan": {
            "attempts": scan["attempts"],
            "gross_dishonour_rate": scan["gross_dishonour_rate"],
            "cure_rate": scan["cure_rate"],
            "net_loss_rate": scan["net_loss_rate"],
            "hard_fail_share": scan["hard_fail_share"],
            "top_payer_concentration": scan["top_payer_concentration"],
            "distinct_payers": scan["distinct_payers"],
            "median_ticket_c": scan["median_ticket_c"],
        },
        "gross_face_c": int(pricing["gross_face_c"]),
        "eligible_face_c": int(pricing["eligible_face_c"]),
        "gross_collections_c": int(pricing["gross_collections_c"]),
        "net_settled_c": int(pricing["net_settled_c"]),
        "fee_drag": pricing["fee_drag"],
        "fee_breakdown": pricing["fee_breakdown"],
        "advance_rate": pricing["advance_rate"],
        "discount_pct": pricing["discount_pct"],
        "cash_today_c": int(pricing["cash_today_c"]),
        "reserve_c": int(pricing["reserve_c"]),
        "wal_months": pricing["wal_months"],
        "term_weeks": pricing["term_weeks"],
        "business_irr": pricing["business_irr"],
        "returns": summarise_returns(pricing.get("distribution", {})),
        "curve": pricing.get("distribution", {}).get("curve", []),
        "weekly_net_c": [int(v) for v in pricing["weekly_net_c"]],
    }
