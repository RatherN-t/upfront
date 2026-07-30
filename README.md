# Upfront

Receivables financing on the Pinch rail, funded by ordinary retail investors.

A business sells committed contract revenue or open invoices at a discount.
Retail investors fund the advance. Collections route back automatically through
Pinch, which Upfront operates as master merchant, so repayment is infrastructure
rather than a promise.

Hackathon prototype. Test mode only. No real money moves.

## Quick start

```bash
python3 tools/check.py check              # figures + tests + guards
python3 tools/check.py install-git-hooks  # once per checkout

cd engine
python3 run.py        # full underwriting report for every book
python3 stress.py     # portfolio distribution and sensitivities
```

Open `prototype.html` in a browser for the product walkthrough.

To connect to a real Pinch sandbox and price a live book end to end:

```bash
export PINCH_APP_ID=...   # from web.getpinch.com.au/api-keys
export PINCH_SECRET=...
python3 integration/seed_sandbox.py
```

## Layout

```
CLAUDE.md              agent operating instructions - read this first
docs/                  architecture, math, risk, regulatory, setup
integration/           live Pinch client, adapter, sandbox seeder, adapter tests
engine/                pricing, fee model, portfolio risk, mock books, tests
tools/                 check harness and guards
.agents/skills/        trace-figure, grill-pricing, pinch-call, demo-check
.githooks/pre-commit   delegates to tools/check.py pre-commit
prototype.html         product visualisation
```

## The two rules

**Every financial figure traces to `engine/FIGURES.json` or to a `[source: ...]`
line.** Enforced by the `figures` guard.

**No yield is stated without its downside.** Mean, 5th percentile and probability
of loss travel together. Enforced by the `claims` guard.

## Headline numbers

Voltride, the reference book: $166,388 eligible face, 2.34% net bad debt,
2.88% Pinch fee drag, $157,808 net settled, $149,378 cash to the business today,
23.56% p.a. effective cost.

Investor outcome across a four-book portfolio, 20,000 correlated-default
simulations: mean 14.72%, median 18.65%, 5th percentile 2.49%, 1st percentile
-22.46%, probability of loss 4.00%.

That distribution is the product. The single number is not.

## What changed from v1

v1 reported a 14.25% investor yield off a model that ignored Pinch processing
fees, treated subscription revenue as a receivable, used an economy-wide default
rate, and quoted a mean with no distribution. All four errors pointed the same
direction. `docs/05-honest-returns.md` has the corrections and what the number
became.
