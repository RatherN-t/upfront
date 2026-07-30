# 05 — Is 14% too good to be true?

You were right to push on this. The short answer is that the number is roughly
defensible as a *mean*, but the way v1 arrived at it was wrong in five separate
places, and every error pointed the same direction. This document shows the
corrections and what the number becomes.

---

## The instinct was correct

Two calibration points that should make anyone uncomfortable with a
low-risk 14%:

- Kriya, formerly MarketInvoice, ran invoice trading at scale and told investors
  to expect a net yield of **4 to 6 per cent**. [source: Financial Innovation, Springer, 2024]
- Prospa, Australia's largest listed SME lender, realised **net bad debt of 5.7%
  of average gross loans in FY22 and 9.9% in FY23**, while charging a portfolio
  yield around **34.8% APR**. [source: bankingday.com on Prospa FY23 accounts; smbloan.com.au on Prospa H1-23 portfolio yield]

Read those together. A specialist SME lender charges roughly 35% and still loses
between a twentieth and a tenth of its book every year. Any structure claiming
to hand investors mid-teens returns out of the same borrower population, with
"business-default-only risk" in reassuring green, deserves exactly the suspicion
you applied.

---

## Five things v1 got wrong

### 1. Processing fees were not in the model at all

This is the big one. Pinch charges **1.00% + $0.30 per direct debit, capped at
$5.00**, plus **$5.00 for every declined bank-account collection**, plus **$1.00
per settlement transfer**. [source: getpinch.com.au/legal/pricinginformation]

v1 priced the advance against gross expected collections and never subtracted
any of it. On Voltride's book that omission is worth:

| | |
|---|---|
| Transaction fees | $3,037 |
| Decline fees | $1,620 |
| Transfer fees | $26 |
| **Total Pinch cost** | **$4,683** |
| **As a share of collections** | **2.88%** |

Against a total v1 discount of about $7,400, the missing fees were roughly
**63% of the entire gross margin.**

### 2. Ticket size and billing cadence were treated as cosmetic

The fixed $0.30 component does not scale down. On a $34.78 weekly debit it is
86 basis points before the percentage part even applies. The $5 decline fee is
14% of that payment's face value.

Same annual revenue, four billing cadences:

| Cadence | Ticket | Pinch drag |
|---|---|---|
| Weekly | $34.78 | **5.65%** |
| Fortnightly | $69.56 | 3.51% |
| Monthly | $150.71 | 2.14% |
| Quarterly | $452.14 | **1.29%** |

**A 4.4× difference in cost from cadence alone, with revenue held constant.**

This inverts the v1 conclusion about which books are good. The gym book, which
looked cleanest on bad debt at 1.57%, bills $15.95 a week and bleeds **4.40%**
to fees. The B2B invoice book, which v1 called the worse asset, has a median
ticket of $18,000 where the $5 cap makes fees essentially free at **0.04%**.

The invoice book is *cheaper to service by two orders of magnitude.* v1 had it
exactly backwards.

### 3. Subscription revenue was modelled as a receivable. It isn't.

An invoice is money owed for work already delivered. The debtor owes it whether
or not the supplier survives. A subscription is money owed for a service **not
yet delivered**. If Voltride fails, the bikes go back, the riders stop paying,
and the stream stops with the business.

v1's loss model implicitly assumed collections continue after business failure.
They mostly don't. The engine now carries this as an explicit parameter:

| Asset class | Continuation on business failure | Loss given default |
|---|---|---|
| Invoice (work done) | 75% | 14% |
| Contract (service pending) | 15% | **47%** |

This single parameter moves loss severity by more than a factor of three, and it
is the strongest technical argument against calling this product "factoring" at
all. Factoring is the purchase of an existing debt. Buying future subscription
revenue is closer to revenue-based financing, which matters legally as well as
economically — see `07-regulatory.md`.

### 4. Business default probability was set from the wrong population

v1 used around 1% a year, near the economy-wide base rate: about **3,556 of over
3.6 million registered Australian companies entered external administration in
Q1 FY2025-26**. [source: Murrays Legal citing ASIC insolvency statistics]

That base rate is the wrong denominator. It includes millions of dormant shells,
and it excludes the fact that businesses seeking receivables finance are
self-selected for cash-flow stress. Prospa's realised losses are the evidence.
The engine now uses **3.5% to 9.0% a year** depending on the book, and treats
that as an input to be defended rather than a constant.

### 5. Expected loss was quoted as a mean with no distribution behind it

Even corrected, a single expected-loss number is the wrong instrument. SME
defaults are correlated — the recession that closes the gym closes the tutoring
studio in the same quarter. A mean cannot show you that.

---

## What the number actually is

The engine now runs a one-factor Gaussian copula Monte Carlo across the
portfolio, the same structure that sits under Basel IRB and CLO models. Asset
correlation is swept because the honest answer is a range, not a point.

**Four-book portfolio, 20,000 simulations, asset correlation 0.15:**

| Statistic | Investor return |
|---|---|
| Mean | 14.72% |
| Median | 18.65% |
| 25th percentile | 13.18% |
| 10th percentile | 7.40% |
| **5th percentile** | **2.49%** |
| **1st percentile** | **−22.46%** |
| Probability of losing money | **4.00%** |
| Probability of underperforming a term deposit | **6.44%** |

So: **14% is about the right mean, and it is not a low-risk 14%.**

Roughly one run in twenty-five loses money outright. One in sixteen does worse
than leaving the cash in a bank. The one-in-a-hundred outcome is a **22.46%**
capital loss. That distribution is what a mid-teens expected return is *supposed*
to look like — if it looked any safer, the number would be wrong.

The problem was never the mean. **The problem is displaying a single figure in
reassuring green next to a "recourse-protected" badge, rather than the
distribution above.** That framing is what makes it sketchy, and it is what has
to change.

---

## Diversification helps the tail, not the mean

Spreading the same capital across N books, correlation 0.15:

| Books | Mean | 5th pct | 1st pct | P(loss) |
|---|---|---|---|---|
| 1 | 10.72% | 3.32% | **−34.05%** | 2.35% |
| 3 | 10.80% | 1.80% | −25.96% | 3.99% |
| 5 | 10.62% | −1.45% | −18.48% | 5.91% |
| 10 | 10.64% | −1.14% | −10.95% | 5.91% |
| 25 | 10.77% | 0.20% | −8.71% | 4.84% |
| 50 | 10.79% | 0.42% | −6.94% | 4.64% |
| 100 | 10.77% | 0.45% | **−6.33%** | 4.54% |

Three things worth saying out loud:

1. **The mean does not move.** Diversification is not free return, it is variance
   reduction. Anyone who tells you otherwise is selling something.
2. **The tail improves enormously and then stops.** One book to twenty-five cuts
   the 1st-percentile loss by about three quarters. Twenty-five to a hundred buys
   almost nothing, because correlation puts a floor under it. **You cannot
   diversify away the economy.**
3. **Diversification converts rare catastrophes into frequent small losses.** The
   probability of *any* loss actually rises from 2.35% to about 5% as you spread.
   Investors find this counterintuitive and it should be stated plainly.

The product implication: **auto-spread should be the default, not a toggle**, and
the marketing claim is "smaller worst case", never "safer".

---

## Where the business's money goes

Voltride pays an effective **23.56% p.a.**, and the investor sees a mean of
around 14.7% with the downside above. The gap is not margin, it is cost:

```
Business pays (IRR on cash received)              23.56% p.a.
  − Pinch processing and decline fees              ~2.88% of collections
  − Upfront platform take (25% of discount)         1.43% per deal
  − expected credit loss                            1.07% p.a.
  − cash drag while capital is idle (18% assumed)  ~2.9% p.a. equivalent
= investor mean                                    14.72% p.a.
```

Cash drag is the least defensible line. It assumes capital sits idle 18% of the
time between deals. Sensitivity:

| Idle share | Investor net |
|---|---|
| 0% | 16.21% |
| 10% | 14.58% |
| 18% | 13.29% |
| 30% | 11.34% |
| 45% | 8.91% |

At a cold-start marketplace with thin deal flow, 30 to 45% idle is realistic for
the first year. **A more honest launch headline is 9 to 13%, not 14.2%.**

---

## The platform cannot fund itself at small scale

Worth knowing before anyone asks about the business model. At a 1.43% take per
deal and 4.7 capital turns a year:

| Deployed | Revenue | Profit at $1.2m opex |
|---|---|---|
| $5,000,000 | $338,366 | −$861,634 |
| $10,000,000 | $676,732 | −$523,268 |
| $20,000,000 | $1,353,464 | $153,464 |
| $50,000,000 | $3,383,659 | $2,183,659 |

**Breakeven is around $17,732,282 deployed.** Below that the platform is
subsidised. An AFSL, a trust account, compliance, engineering and two-sided
acquisition do not run on less. This is a real constraint and it is better to
name it than to be caught by it.

---

## What to change in the product

1. **Stop showing a single yield figure.** Show mean, 5th percentile and
   probability of loss together, always. The `claims` guard in `tools/guards.py`
   enforces this mechanically across the docs; the prototype should match.
2. **Fix the amortisation error.** $1,000 in Voltride returns about $37 of
   profit, not $71. Capital comes back weekly.
3. **Add the fee-drag panel to the analysis screen.** It is the most novel thing
   the engine computes and removing it is how the model quietly becomes
   dishonest again.
4. **Default to auto-spread**, and describe it as reducing the worst case rather
   than reducing risk.
5. **Lead with invoices, not subscriptions**, or at minimum price them
   differently and say why. Work already delivered survives business failure;
   service not yet delivered does not.
6. **Register PPSR security** over purchased receivables. It moves recovery from
   about 20% to about 45% and is the cheapest risk reduction available.

---

## The sentence to have ready

> A specialist SME lender in this market charges about 35% and still writes off
> between 5 and 10% of its book a year. We charge about 24% because we collect
> on the rail instead of hoping, and we hand investors a mean in the low teens
> with a one-in-twenty-five chance of losing money. That is not a safe 14%. It is
> a correctly priced one, and we show people the distribution rather than the
> headline.
