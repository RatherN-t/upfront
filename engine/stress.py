"""Portfolio distribution and the sensitivities that matter."""
from pricing_engine import price_deal, RiskPolicy, p
from portfolio_risk import Position, PortfolioParams, simulate, diversification_curve
from mock_books import ALL_BOOKS

deals = {b.name: price_deal(b) for b in ALL_BOOKS}
pos = [Position(b.name, deals[b.name]["cash_today_c"],
                deals[b.name]["investor_gross_irr"],
                deals[b.name]["wal_months"] / 12,
                b.business_pd_annual, b.asset_class) for b in ALL_BOOKS]

print("PORTFOLIO OUTCOME — 4 books, 20,000 correlated-default simulations")
print("-" * 84)
print(f"{'rho':>6}{'mean':>9}{'p50':>9}{'p25':>9}{'p10':>9}{'p5':>9}{'p1':>10}"
      f"{'P(loss)':>10}{'P(<4.5%)':>11}")
for rho in (0.05, 0.15, 0.25, 0.40):
    r = simulate(pos, PortfolioParams(rho=rho), n=20000)
    print(f"{rho:>6.2f}{p(r['mean'],1):>9}{p(r['p50'],1):>9}{p(r['p25'],1):>9}"
          f"{p(r['p10'],1):>9}{p(r['p5'],1):>9}{p(r['p1'],1):>10}"
          f"{p(r['prob_negative'],1):>10}{p(r['prob_below_term_deposit'],1):>11}")

print()
print("DIVERSIFICATION — same capital across N books, rho 0.15")
print("-" * 84)
print(f"{'books':>7}{'mean':>10}{'p5':>10}{'p1':>11}{'P(loss)':>11}")
for k, r in diversification_curve(pos[0], PortfolioParams(rho=0.15)).items():
    print(f"{k:>7}{p(r['mean'],1):>10}{p(r['p5'],1):>10}{p(r['p1'],1):>11}"
          f"{p(r['prob_negative'],1):>11}")
print("  the mean does not move — diversification buys variance, not return")
print("  and it plateaus: you cannot diversify away the economy")

print()
print("CASH DRAG — share of investor capital idle between deals (Voltride)")
print("-" * 84)
for cd in (0.0, 0.10, 0.18, 0.30, 0.45):
    r = price_deal(ALL_BOOKS[0], None, RiskPolicy(cash_drag=cd))
    print(f"  idle {cd*100:>4.0f}%   ->   {p(r['investor_after_cash_drag'])}")
print("  a cold-start marketplace runs 30-45% idle in year one")

print()
print("CONTINUATION — what survives business failure (the key assumption)")
print("-" * 84)
for cont in (0.05, 0.15, 0.35, 0.75):
    rp = RiskPolicy()
    rp.continuation_on_failure = {"contract": cont, "invoice": cont}
    r = price_deal(ALL_BOOKS[0], None, rp)
    print(f"  continuation {cont*100:>3.0f}%   LGD {p(r['lgd'],1):>7}   "
          f"net {p(r['investor_after_cash_drag'])}")

print()
print("RECOURSE RECOVERY — unsecured vs PPSR-registered")
print("-" * 84)
for lbl, rec in (("no security 5%", 0.05), ("unsecured 20%", 0.20), ("PPSR 45%", 0.45)):
    rp = RiskPolicy(recourse_recovery=rec, recourse_recovery_with_ppsr=rec)
    r = price_deal(ALL_BOOKS[0], None, rp)
    print(f"  {lbl:<16} LGD {p(r['lgd'],1):>7}   net {p(r['investor_after_cash_drag'])}")
