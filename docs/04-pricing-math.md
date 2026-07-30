# 04 — Pricing math

Every figure here is produced by `engine/pricing_engine.py`. Regenerate with
`python3 tools/check.py figures`.

## Sequence

```
1. eligible_face    = screen(receivables)
2. gross_collections= eligible_face * (1 - net_bad_debt)
3. fee_drag         = pinch_fees(ticket, cadence, dishonour_rate) / gross
4. NET SETTLED      = gross_collections * (1 - fee_drag)     <- price off THIS
5. advance_rate     = min(95%, 1 - net_bad_debt - 3% buffer)
6. WAL              = sum(t * cf_t) / sum(cf_t)
7. discount         = net_settled * rate_per_30d * WAL_months
8. cash_today       = min(net_settled * advance_rate, net_settled - discount)
9. reserve          = net_settled - discount - cash_today
10. investor_income = discount * 75%     platform = discount * 25%
```

Two decisions worth defending.

**Step 4 — price against net settled cash, not gross.** The business is already
paying Pinch fees today whether or not it factors; they are netted from its
settlements right now. Advancing against gross would silently transfer that cost
to the investor. Advancing against net keeps the yield honest and reduces the
cash the business receives, which is the truthful outcome.

**Step 7 — rate times WAL, not rate times term.** A 26-week amortising book is
not 26 weeks of capital outstanding; money starts returning in week 1. WAL for a
flat 26-week schedule is 3.12 months, not 6. Charging on term would nearly double
the price for time the money is not out.

## Policy dials

| Dial | Value | Anchor |
|---|---|---|
| Base discount | 1.30% of face per 30 days (grade A) | AU invoice finance fees 1.5-4.5% of face; P2P discount rates 0.8-1.5% per 30 days [source: smartsmssolutions.com; InvoiceInterchange] |
| Grade spread | A 0, A- +0.17, B+ +0.40, B +0.70, C +1.20 (pts per 30d) | |
| Max advance | 95% | AU debtor finance commonly 80-85%; international 80-95% [source: money.com.au; SMBCompass] |
| Reserve buffer | 3% above expected loss | |
| Platform take | 25% of discount | Pipe charged up to 1% per side [source: founderpath.com] |

## Voltride, worked

```
Gross receivables on the rail                      $180,856
  less cancel-anytime and unmandated contracts
ELIGIBLE FACE                                      $166,388

Bad-debt scan: 6.76% gross dishonours, 65.37% cured   -> 2.34% net
Gross expected collections                         $162,491

Pinch fee drag  (median ticket $34.78, 26 weeks)
   transaction fees                                  $3,037
   decline fees                                      $1,620
   transfer fees                                        $26
   total                             $4,683  =  2.88%
NET SETTLED                                        $157,808

Advance rate  min(95%, 1 - 2.34% - 3.00%)           94.66%
WAL                                              3.12 months
Discount  $157,808 x 1.70%/30d x 3.12mo              $8,358   (5.30%)
   platform 25%                                      $2,089
   investor 75%                                      $6,268

CASH TO VOLTRIDE TODAY                             $149,378
Reserve released at term end                            $72
Business effective cost                             23.56% p.a.
```

## Investor side

```
Outlay                                             $149,378
Gross IRR                                            17.28% p.a.
  less expected credit loss
     PD 4.50%/yr -> 1.19% over 3.12mo life
     continuation on failure 15%, recovery 45% -> LGD 46.75%
     drag                                            -1.07% p.a.
Net IRR                                              16.21% p.a.
  less cash drag while idle (18% assumed)
REALISED                                             13.29% p.a.
```

That is the single-deal expected value. It is not what an investor should be
shown. The portfolio distribution in `05-honest-returns.md` is: mean 14.72%,
5th percentile 2.49%, 1st percentile -22.46%, probability of loss 4.00%.

## All four books

| Book | Class | Grade | Net BD | Fee drag | Net settled | Discount | Cash today | Biz cost | Inv mean |
|---|---|---|---|---|---|---|---|---|---|
| Voltride | contract | B+ | 2.34% | 2.88% | $157,808 | 5.30% | $149,378 | 23.56% | 13.29% |
| Northline | contract | B | 1.57% | 4.40% | $120,971 | 6.23% | $113,433 | 28.42% | 16.36% |
| Studio 04 | contract | C | 5.59% | 2.39% | $114,999 | 6.06% | $105,119 | 38.90% | 20.66% |
| Kerrigan | invoice | C | 7.94% | 0.04% | $132,776 | 3.75% | $118,255 | 43.11% | 22.78% |

Read the fee-drag column against the net-bad-debt column. Northline has the
**cleanest** payment history and the **worst** economics, because it bills
$15.95 a week. Kerrigan has the dirtiest history and near-zero fee drag, because
its median ticket is $18,000 and the $5 cap makes collection almost free.

## The amortisation error to fix in the prototype

The current site computes investor return as `amount x yield x months / 12`.
That treats the whole principal as outstanding for the full term. It is not —
the book amortises weekly.

For $1,000 in Voltride the profit is about **$34.50**, not $71. The site
overstates by roughly 100%.

Three fixes, pick one:

- **Correct it.** "About $34.50. Your capital returns weekly rather than sitting
  locked up, which is why the dollar figure looks smaller than the rate."
- **Show both.** Return on capital 13.29% p.a. Cash profit $34.50. Capital fully
  returned by week 26.
- **Add auto-reinvest.** Repayments roll into the next book, the annual rate
  becomes achievable, and the bug becomes a retention feature.

Whichever you choose, the figure must sit next to its downside. A stake of this
size carries a 4.00% probability of loss and a 1st-percentile outcome of
-22.46%; showing the profit without the risk is the problem this repo exists to
avoid.
