# Upfront

Hackathon prototype, test mode only: receivables financing on the Pinch rail,
funded by ordinary retail investors.

A business sells committed contract revenue or open invoices at a discount.
Retail investors fund the advance. Collections route back automatically through
Pinch, which Upfront operates as master merchant, so repayment is infrastructure
rather than a promise.

Hackathon prototype. Test mode only. No real money moves.

## Quick start

**The running product** — a business onboards, gets underwritten and opens a
funding round; investors browse rounds and invest:

```bash
python3 -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" httpx
(cd webapp/frontend && npm install)

# terminal 1
cd webapp/api && ../../.venv/bin/python -m uvicorn main:app --port 8017
# terminal 2
cd webapp/frontend && npm run dev          # -> http://localhost:5173

.venv/bin/python webapp/seed_demo.py       # three businesses, rounds open
```

Full detail, including the live-vs-simulated distinction, in
`webapp/README.md`.

**The engine on its own:**

```bash
python3 tools/check.py check              # figures + tests + guards
python3 tools/check.py install-git-hooks  # once per checkout

cd engine
python3 run.py        # full underwriting report for every book
python3 stress.py     # portfolio distribution and sensitivities
```

`prototype.html` is the original static walkthrough, kept for the pitch.

To connect to a real Pinch sandbox and price a live book end to end:

```bash
export PINCH_APP_ID=...   # from web.getpinch.com.au/api-keys
export PINCH_SECRET=...
python3 integration/seed_sandbox.py
```

Without those two variables the app still runs, against an in-process
simulator that is labelled as such everywhere it appears.
`docs/10-get-credentials-now.md` is the click-path for getting them.

## Layout

```
CLAUDE.md              agent operating instructions - read this first
docs/                  architecture, math, risk, regulatory, setup
webapp/                the running product: FastAPI + SQLite, React frontend
integration/           live Pinch client, adapter, sandbox seeder, adapter tests
engine/                pricing, fee model, portfolio risk, mock books, tests
tools/                 check harness and guards
.agents/skills/        trace-figure, grill-pricing, pinch-api, demo-check
.githooks/pre-commit   delegates to tools/check.py pre-commit
prototype.html         static product walkthrough (pre-dates webapp/)
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
