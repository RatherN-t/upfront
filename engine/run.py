"""Full underwriting report for every book."""
from pricing_engine import price_deal, platform_viability, d, p
from mock_books import ALL_BOOKS
from fees import cadence_comparison

for b in ALL_BOOKS:
    r = price_deal(b)
    s, sc = r["scan"], r["screen"]
    print("=" * 76)
    print(f"{b.name}  —  {b.sector}   [{b.asset_class}]   Rail Score {r['grade']}")
    print("-" * 76)
    print(f"  attempts analysed        {s['attempts']:,}")
    print(f"  gross dishonour rate     {p(s['gross_dishonour_rate'])}")
    print(f"  cure rate                {p(s['cure_rate'],1)}")
    print(f"  NET BAD DEBT             {p(s['net_loss_rate'])}")
    print(f"  hard-fail share          {p(s['hard_fail_share'],1)}")
    print(f"  top payer concentration  {p(s['top_payer_concentration'],1)}")
    print(f"  median ticket            ${s['median_ticket_c']/100:,.2f}")
    print()
    print(f"  gross face               {d(sc['gross_face_c'])}")
    print(f"  concentration haircut   -{d(sc['concentration_haircut_c'])}")
    print(f"  ELIGIBLE FACE            {d(r['eligible_face_c'])}")
    print(f"  gross collections        {d(r['gross_collections_c'])}")
    print()
    print(f"  PINCH FEE DRAG           {p(r['fee_drag'])}")
    print(f"     transaction fees      {d(r['fee_breakdown']['txn_fees_c'])}")
    print(f"     decline fees          {d(r['fee_breakdown']['decline_fees_c'])}")
    print(f"     transfer fees         {d(r['fee_breakdown']['transfer_fees_c'])}")
    print(f"  NET SETTLED              {d(r['net_settled_c'])}")
    print()
    print(f"  advance rate             {p(r['advance_rate'],1)}")
    print(f"  discount rate            {p(r['discount_rate_pm'])} / 30 days")
    print(f"  weighted average life    {r['wal_months']:.2f} months ({r['term_weeks']} wks)")
    print(f"  total discount           {d(r['discount_c'])} = {p(r['discount_pct'])}")
    print(f"     platform              {d(r['platform_c'])}")
    print(f"     investor              {d(r['investor_income_c'])}")
    print()
    print(f"  CASH TO BUSINESS TODAY   {d(r['cash_today_c'])}")
    print(f"  reserve at term end      {d(r['reserve_c'])}")
    print(f"  business effective cost  {p(r['business_irr'],2)} p.a.")
    print()
    print(f"  investor gross IRR       {p(r['investor_gross_irr'])}")
    print(f"    PD {p(r['pd_annual'],1)}/yr -> {p(r['pd_life'])} over life")
    print(f"    continuation {p(r['continuation'],0)} -> LGD {p(r['lgd'],2)}")
    print(f"    credit loss drag      -{p(r['loss_drag_annual'])}")
    print(f"  net IRR                  {p(r['investor_net_irr'])}")
    print(f"  after cash drag          {p(r['investor_after_cash_drag'])}")
    print("  (single-deal expectation — see stress.py for the distribution)")
    print()

print("=" * 76)
print("PINCH FEE DRAG BY BILLING CADENCE (identical annual revenue)")
print("-" * 76)
for k, v in cadence_comparison(3478 * 52, 0.066, 0.68).items():
    print(f"  {k:<13} ticket ${v['ticket_c']/100:>8,.2f}   {v['n_txns']:>3} txns   "
          f"drag {p(v['drag'])}")

print()
print("=" * 76)
print("PLATFORM VIABILITY  (opex $1.2m: AFSL, trust account, engineering, CAC)")
print("-" * 76)
deals = [price_deal(b) for b in ALL_BOOKS]
for dep in (5_000_000_00, 10_000_000_00, 20_000_000_00, 50_000_000_00):
    v = platform_viability(deals, dep)
    print(f"  deployed {d(dep):>13}   revenue {d(v['annual_revenue_c']):>12}   "
          f"profit {d(v['profit_c']):>13}")
v = platform_viability(deals, 10_000_000_00)
print(f"  breakeven AUM {d(v['breakeven_deployed_c'])} "
      f"at {p(v['take_rate_per_deal'])} take and {v['turns_per_year']:.2f} turns/yr")
