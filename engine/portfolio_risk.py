"""
Portfolio risk — correlated default Monte Carlo
===============================================

Single-deal expected loss is the wrong tool for the question "is 14% too good
to be true". Expected loss tells you the MEAN. What an investor actually cares
about is the DISTRIBUTION, and specifically the left tail, because SME defaults
are correlated: the recession that kills one gym kills the tutoring studio too.

This uses the standard one-factor Gaussian copula (the same structure that sits
under Basel IRB and every CLO model):

    A_i = sqrt(rho) * M  +  sqrt(1 - rho) * e_i

    M     ~ N(0,1)   systematic factor (the economy)
    e_i   ~ N(0,1)   idiosyncratic factor (this business)
    default_i  <=>  A_i < Phi^-1(PD_i)

rho is the asset correlation. Basel's IRB formula for corporate exposures uses
0.12-0.24, with an explicit SME size adjustment pushing smaller firms toward the
lower end. Empirically, small firms are less correlated with the market than
large ones but MORE correlated with each other in a credit crunch. We run a
range and report all of it, because the honest answer is a range.

Two structural features specific to this product are modelled explicitly:

  continuation   what fraction of the remaining stream still collects after the
                 business fails. For an invoice the work is done and the debtor
                 still owes it (~75%). For a subscription the service stops and
                 the stream stops with it (~15%). This is the single biggest
                 driver of loss severity and it is NOT a detail.

  recovery       what you get back from an insolvent business under recourse.
                 Unsecured you are behind employees and the ATO. With a PPSR
                 registration over the receivables you are materially better off.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Dict


def _phi_inv(u: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    dd = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
          3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if u < pl:
        q = math.sqrt(-2 * math.log(u))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    if u > ph:
        q = math.sqrt(-2 * math.log(1 - u))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    q = u - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


@dataclass
class Position:
    name: str
    principal_c: float
    gross_irr: float          # annualised, before losses
    wal_years: float
    pd_annual: float
    asset_class: str


@dataclass
class PortfolioParams:
    rho: float = 0.15                  # asset correlation
    continuation: Dict[str, float] = None
    recovery_mean: float = 0.45        # PPSR-registered
    recovery_sd: float = 0.15
    # in a systemic downturn customer bad debt also rises; this scales the
    # portion of the stream that fails even WITHOUT business default
    stress_beta: float = 0.020
    cash_drag: float = 0.18

    def __post_init__(self):
        if self.continuation is None:
            self.continuation = {"invoice": 0.75, "contract": 0.15}


def simulate(positions: List[Position], params: PortfolioParams,
             n: int = 20000, seed: int = 7,
             include_samples: bool = False) -> Dict:
    """`include_samples` adds the raw sorted returns under "samples".

    Off by default: the samples are large, and every caller that only wants
    the summary (docs, FIGURES.json, the CLI report) should stay unaffected.
    The web app turns them into a histogram, because the *shape* of the
    distribution is the honest picture and a mean alone is not.
    """
    rng = random.Random(seed)
    total_p = sum(p.principal_c for p in positions)
    if total_p == 0:
        return {}

    thresholds = {}
    for pos in positions:
        pd_life = 1 - (1 - pos.pd_annual) ** pos.wal_years
        pd_life = min(max(pd_life, 1e-9), 1 - 1e-9)
        thresholds[pos.name] = _phi_inv(pd_life)

    wal_w = sum(p.principal_c * p.wal_years for p in positions) / total_p
    gross_w = sum(p.principal_c * p.gross_irr for p in positions) / total_p

    returns = []
    for _ in range(n):
        M = rng.gauss(0, 1)
        loss_c = 0.0
        for pos in positions:
            A = math.sqrt(params.rho) * M + math.sqrt(1 - params.rho) * rng.gauss(0, 1)
            if A < thresholds[pos.name]:
                cont = params.continuation[pos.asset_class]
                rec = min(0.95, max(0.0, rng.gauss(params.recovery_mean,
                                                   params.recovery_sd)))
                # on default, on average half the principal is still outstanding
                outstanding = pos.principal_c * rng.uniform(0.25, 0.85)
                loss_c += outstanding * (1 - cont) * (1 - rec)
        # systematic stress also lifts ordinary customer bad debt
        extra = max(0.0, -M) * params.stress_beta
        loss_c += total_p * extra

        loss_frac = loss_c / total_p
        net = gross_w - (loss_frac / wal_w if wal_w else 0)
        returns.append(net * (1 - params.cash_drag))

    returns.sort()

    def pct(q):
        return returns[min(len(returns) - 1, int(q * len(returns)))]

    return {
        "n": n,
        **({"samples": returns} if include_samples else {}),
        "mean": sum(returns) / len(returns),
        "p50": pct(0.50), "p25": pct(0.25), "p10": pct(0.10),
        "p5": pct(0.05), "p1": pct(0.01),
        "worst": returns[0], "best": returns[-1],
        "prob_negative": sum(1 for r in returns if r < 0) / len(returns),
        "prob_below_5pct": sum(1 for r in returns if r < 0.05) / len(returns),
        "prob_below_term_deposit": sum(1 for r in returns if r < 0.045) / len(returns),
        "gross_weighted": gross_w,
        "wal_weighted": wal_w,
    }


def diversification_curve(base: Position, params: PortfolioParams,
                          sizes=(1, 3, 5, 10, 25, 50, 100), n: int = 8000) -> Dict:
    """How much does spreading across more books actually help?
    Correlation puts a floor on this — you cannot diversify away the economy."""
    out = {}
    for k in sizes:
        pos = [Position(f"b{i}", base.principal_c / k, base.gross_irr,
                        base.wal_years, base.pd_annual, base.asset_class)
               for i in range(k)]
        out[k] = simulate(pos, params, n=n, seed=11 + k)
    return out
