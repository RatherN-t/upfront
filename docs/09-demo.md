# 09 — Demo

## The 60 seconds

| Time | Beat | The line |
|---|---|---|
| 0-8s | Voltride's book on the rail | "Their bank sees a P&L. We see 4,820 payment attempts." |
| 8-22s | Analysis: bad-debt scanner **and fee-drag panel** | "6.76% of payments fail. Two thirds cure on retry. Net 2.34%. And this book loses another 2.88% to transaction fees, because it bills $34.78 a week." |
| 22-32s | Offer: $149,378 today, stream-to-lump animation | |
| 32-46s | Investor view with the distribution, not a single number | "Mean 14.7%. One run in twenty-five loses money. We show people that." |
| 46-56s | Collections: soft fail cures, hard fail fires the recourse direct debit with a real `pmt_` id | |
| 56-60s | Close | "Every other lender hands over the money and hopes. We collect the revenue ourselves, on the same rail. Repayment isn't a promise, it's the plumbing." |

Do not demo the invoice book in the 60 seconds. Keep it for Q&A — a second asset
class in your pocket when a judge asks "does this generalise?" is worth more than
eight seconds of screen time.

## Before you run it

```bash
python3 tools/check.py check      # figures, tests, guards
```

If that fails, the prototype is showing numbers the engine no longer produces.

The mock generator is seeded. Two consecutive runs must be identical. If they
diverge, the seed is not being respected and the demo will drift on stage.

## Judge Q&A

**"Why can't a bank do this?"**
A bank underwrites a P&L the business typed in. We underwrite 4,820 payment
attempts we watched happen, and we can tell a soft dishonour that cures from a
hard one that never will. A bank also cannot collect on the customer's mandate.
We can, because we are the merchant of record.

**"Isn't 14% too good to be true?"**
It is the mean, not a floor. The 5th percentile is 2.49%, the 1st is -22.46%,
and about one run in twenty-five loses money. Prospa charges around 35% in this
market and still writes off 5 to 10% a year. We charge 24% because we collect
instead of hoping. That is a correctly priced risk, not a safe one.

**"Why is Pinch not just a payment button?"**
Three jobs. Underwriting data source — nobody else can read this history.
Collection engine — customers never re-authorise. Settlement rail — Transfers
arrive net of dishonours. Take Pinch out and there is no product. And the fee
schedule is itself an underwriting input: the $5 cap means a $18,000 invoice
costs 0.04% to collect and a $16 gym debit costs 4.40%.

**"What happens to the receivable if the business fails?"**
Depends what you bought. An invoice is for work already done, so the debtor still
owes it — we model 75% continuation. A subscription is for service not yet
delivered, so it dies with the business — 15%. That is why the two asset classes
price differently, and it is the main reason we are careful about calling the
subscription product factoring.

**"What's your biggest risk?"**
Correlation. Recourse is only worth what the business is worth, and customer
defaults and business defaults spike in the same recession. Diversification cuts
the tail by about three quarters from one book to twenty-five and then stops,
because you cannot diversify away the economy.

**"Can the platform make money?"**
Not below about $17.7m deployed. At a 1.43% take and 4.7 turns a year, breakeven
against a $1.2m cost base is around there. Worth knowing before someone asks.
