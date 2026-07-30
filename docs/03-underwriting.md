# 03 — Underwriting

Three stages: screen out what cannot be collected, measure what is left, grade it.

## Stage 1 — eligibility screen

| Rule | Threshold | Why |
|---|---|---|
| Active mandate or agreement | Required | No stored payment method, no collection mechanism |
| Committed term (contracts) | Required | Cancel-anytime revenue is a hope, not a receivable |
| Payer hard-fail history | Exclude | `blocked-by-bank` rejects all future attempts |
| Disputed or credit-noted | Exclude | Standard factoring exclusion |
| Forward horizon | 26 weeks | Do not buy revenue you cannot see |
| Days past due | 90 | Standard |
| Single-payer concentration | Cap at 20% | The rule that actually saves you |

The concentration cap is not decoration. On the Kerrigan invoice book one debtor
is 36% of the ledger, and the cap removes $43,420 from a $187,700 screened
ledger. Australian benchmarking guidance flags review at roughly 20%.
[source: scalesuite.com.au debtor days benchmarks]

## Stage 2 — the bad-debt scanner

Read from `GET /payments/processed` (paged), **value-weighted, never count-weighted.**
A book with many tiny failures and a few large successes looks healthy on counts
and terrible on value.

```
gross_dishonour_rate = dishonoured_value / total_attempted_value
cure_rate            = value of dishonours later settled / dishonoured_value
NET BAD DEBT         = gross_dishonour_rate * (1 - cure_rate)
```

Sanity check against published data: direct debit fails about 6.5% of the time
and intelligent retry recovers around 70%, implying roughly 1.95% net.
[source: paychoice.com.au; GoCardless] The engine produces 2.34% for Voltride and
1.57% for Northline, which brackets it correctly.

**The soft/hard split is the real signal.** Two businesses can both show 7% gross
dishonours. If one is 90% `insufficient-funds` that cures on retry and the other
is 60% `blocked-by-bank`, they are completely different credits. No lender
working from accounting exports can see this distinction.

## Stage 3 — fee drag as an underwriting input

The finding that inverted v1's conclusions. Pinch charges 1.00% + $0.30 per
direct debit capped at $5, plus $5 per decline. [source: getpinch.com.au/legal/pricinginformation]
The fixed components do not scale down.

Same annual revenue, four cadences:

| Cadence | Ticket | Drag |
|---|---|---|
| Weekly | $34.78 | 5.65% |
| Fortnightly | $69.56 | 3.51% |
| Monthly | $150.71 | 2.14% |
| Quarterly | $452.14 | 1.29% |

**Cadence alone moves cost by 4.4x.** A gym billing $15.95 weekly loses 4.40% to
fees. A fitout business billing $18,000 invoices loses 0.04%.

This is a genuinely Pinch-native underwriting factor. It is invisible in a P&L
and it materially changes which books are worth funding. It is also actionable
advice you can give a business for free: move from weekly to monthly billing and
you keep about 3.5% more of your own revenue.

## Grading

Additive score to A / A- / B+ / B / C. Fee drag is a scoring input, not a footnote.

| Signal | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Net bad debt | under 1.5% | under 2.5% | under 4% | 4% or more |
| Top payer concentration | under 10% | under 20% | 20% or more | |
| Months trading on rail | 24 or more | 12 or more | under 12 | |
| Hard-fail share | under 25% | 25% or more | | |
| **Pinch fee drag** | under 1.5% | under 3% | 3% or more | |

Grade sets the spread over the base discount rate.

## What the engine cannot see

State these before a judge finds them.

- **Fraud.** Fake payers, related-party receivables, double-pledged books. Rail
  data helps — you see actual collections, not claimed ones — but a determined
  operator can run real money through real customers. Mitigations: exclude
  related-party payers, require six months of history, cap first facilities.
- **Business quality.** You see cash in, not costs, margins or the ATO debt that
  will kill them. Outstanding ATO debt is a major red flag for Australian invoice
  financiers and it is invisible on the rail. [source: broker.com.au invoice finance guide]
- **Forward demand.** A gym with perfect payment history and no new members is
  dying, and the rail shows you that only after it happens.
- **Correlation.** The scanner is per-book. Risk is portfolio-level. See
  `engine/portfolio_risk.py`.
