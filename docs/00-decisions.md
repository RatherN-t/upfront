# 00 — Decisions

Short record of what was decided and what would reverse it.

### D1 — Master merchant with managed merchants underneath
Upfront holds one credential set; each business is a managed merchant addressed
by `Current-Merchant`. **Reverses if** Pinch will not enable managed-merchant
access on the sandbox account. Fallback is read-only OAuth per merchant, which
loses collection control and most of the thesis.

### D2 — Settlement routes to an Upfront collections account
Set via the managed merchant's disbursement bank account. **Reverses if** Pinch
exposes a per-payment application fee to master merchants, which would be
cleaner. Both questions are open on Slack.

### D3 — Recourse is a direct-debit mandate, not a clause
The business becomes a Payer of Upfront with an authorised DDR at funding.
Recourse is `POST /payments`. **Reverses if** legal advice says taking a DDR from
a business you have just bought receivables from creates a characterisation
problem.

### D4 — Price against net settled cash, not gross collections
Pinch fees come out before the money arrives. Advancing against gross would push
that cost silently onto investors.

### D5 — Fee drag is an underwriting input and a grading factor
Cadence and ticket size move cost by 4.4x on identical revenue. This is the most
novel thing the engine computes.

### D6 — Two asset classes with different continuation factors
Invoice 75%, contract 15%. **This is the highest-leverage assumption in the
model.** If it is wrong, every loss number is wrong.

### D7 — Returns are shown as a distribution, never a point
Mean, 5th percentile and probability of loss together. Enforced by the `claims`
guard.

### D8 — Business default probability comes from the financed population
3.5-9.0% a year, not the economy-wide base rate. Justified by Prospa's realised
net bad debt of 5.7% FY22 and 9.9% FY23. [source: bankingday.com on Prospa FY23]

### D9 — Synthetic books calibrated to public sources
No real SME ledger is obtainable or needed. Every parameter traces to
`06-market-data.md`.

### D10 — Stay in Pinch test mode
No live compliance for the hackathon. Build the compliance-status panel against
the three flags instead.
