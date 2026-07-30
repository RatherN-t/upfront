# HANDOFF.md

Read this first, then `CLAUDE.md`, then start work. This file is the bridge
between the design/analysis session that produced this repo and the build
session you're starting now.

## What you're picking up

**Upfront** — a receivables-financing marketplace on Pinch Payments, for a
hackathon (Pinch × Founders Union, final submission Fri 31 July 11:59pm). A
business sells committed contract revenue or open invoices at a discount; retail
investors fund the advance from $500; collections route back on the Pinch rail,
which Upfront operates as master merchant.

The previous sessions did the analytical work AND the connection layer: a
pricing/risk engine, a corrected returns model, a full doc set, a check harness
with guards, a static HTML prototype, and now a runnable Pinch client that
authenticates, creates managed merchants, reads books, schedules payments with
application fees, and seeds a real sandbox book end to end via Time-Travel. What
remains is wiring the prototype to that client and building the webhook
receiver.

## State of the repo

```
CLAUDE.md              agent operating instructions — the rules that govern edits
README.md              orientation
HANDOFF.md             this file
docs/00..09            decisions, architecture, pinch integration, underwriting,
                       pricing math, honest returns, market data, regulatory,
                       external setup, demo
engine/
  fees.py              Pinch fee model (published pricing, integer cents)
  pricing_engine.py    scan → screen → fee drag → grade → price. IRR/WAL. viability
  portfolio_risk.py    one-factor Gaussian copula Monte Carlo (correlated defaults)
  mock_books.py        4 deterministic Pinch-shaped books (seed 1729)
  test_engine.py       11 tests, each guarding a property that broke once
  run.py               full underwriting report for every book
  stress.py            portfolio distribution + sensitivities
  FIGURES.json         generated — the single source of truth for doc figures
tools/
  check.py             the one entrypoint: figures | tests | guards | prove | check
  guards.py            figures, pinch_api, money_type, no_secrets, claims, skills
.agents/skills/        trace-figure, grill-pricing, pinch-call, demo-check
.githooks/pre-commit   delegates to tools/check.py pre-commit
prototype.html         static product walkthrough (S0→S8), self-contained
```

Everything currently passes:

```bash
python3 tools/check.py check    # figures + tests + guards, all green
python3 tools/check.py prove    # proves 2 guards catch real regressions
```

## The two rules you must not break

They're in `CLAUDE.md` in full. Short version:

1. **Every financial figure traces to `engine/FIGURES.json` or a `[source: ...]`
   line.** If you change an assumption, run `python3 tools/check.py figures` and
   update the prose. Never hand-edit a number to match a doc. The `figures` guard
   fails the build otherwise.
2. **No yield is ever shown without its downside** (mean + 5th percentile +
   probability of loss). The `claims` guard enforces this in the docs; hold the
   UI to the same standard.

## The headline finding, so you don't undo it

The user asked whether a low-risk 14% was sketchy. It was. v1 made five errors,
all inflating returns: it ignored Pinch fees, treated subscription revenue as a
receivable, used the economy-wide default rate, ignored cash drag, and quoted a
mean with no distribution. Corrected, the four-book portfolio returns a **mean
of 14.72%, a 5th percentile of 2.49%, a 1st percentile of −22.46%, and a 4.00%
probability of loss.** The number is a correctly priced risk, not a safe one.
`docs/05-honest-returns.md` is the anchor. Don't let a future edit quietly revert
any of the five.

## What to build next, in order

The engine and analysis are done. The build work is turning the static prototype
into something that talks to Pinch. Suggested order:

### 1. Unblock Pinch access — do this before writing code
`docs/08-external-setup.md` has the exact Slack message. The critical item is
managed-merchant access on the sandbox, plus two architecture-deciding questions
(can the master set a managed merchant's disbursement account; is there a
per-payment application fee). You cannot validate the core architecture until
these are answered. This is a human task — flag it to the user immediately.

### 2. The Pinch client — DONE, in `integration/`
`pinch_client.py` wraps the API so `Current-Merchant` is structurally impossible
to omit (`as_merchant()` scope), rejects float money, caches tokens, and refuses
Time-Travel in live mode. `adapter.py` maps live JSON to engine `Book` objects.
`seed_sandbox.py` creates a real test merchant with real payment history and
prices it. Use the `pinch-api` skill for any change here. What's left: add a
webhook receiver (signature verify, evt_ idempotency, week-as-state-machine).

### 3. Seed the sandbox with real failures
Use the `#dishonour-code` trick (`docs/08` §5) to push real payments through the
real sandbox that fail with real codes, so a real webhook handler processes them.
This is the difference between a demo that looks built and one that is.

### 4. Webhook handler
Signature verification before parsing, idempotent on `evt_` id, and a
week-as-state-machine model because settlements reverse days later. All three are
non-negotiable and all three are in `docs/02`.

### 5. Wire the prototype to live data
The prototype is currently hardcoded to `FIGURES.json`-consistent numbers. Feed
it the engine output and, where possible, live sandbox data. Keep the fee-drag
panel and the distribution chart — those are the two most defensible things on
screen.

### 6. Before submitting
Run the `demo-check` skill. Time the 60 seconds. `docs/09-demo.md` has the script
and the Q&A.

## On Remotion / Hyperframe for the motion design

You asked whether you can use these inside the HTML itself. Here's the accurate
picture:

**Remotion is React, not drop-in HTML.** It's a framework for defining video as
React components. You can't paste it into `prototype.html` the way you'd add a
`<script>` tag — it needs a React build step (bundler, `npm`, JSX). So "within
the HTML in itself" is a no for the current single-file prototype.

There are two real ways to use it, and one is genuinely worth it:

- **`@remotion/player`** embeds a Remotion composition in a *React app* and plays
  it live in the browser, with props you can change at runtime. This is the right
  tool if you rebuild the prototype as a small React/Vite app — which you may want
  to anyway, since the current prototype is one big vanilla-JS file and will get
  unwieldy. The player is lightweight and doesn't need any server.
- **Server-side render to MP4** (`@remotion/renderer` / Lambda) if you want a
  polished 60-second sizzle video to submit *alongside* the live demo. This is the
  strongest fit: the hackathon asks for a 60-second demo video, and Remotion is
  purpose-built for programmatic, data-driven video. You could drive it straight
  off `FIGURES.json` so the video numbers can never drift from the engine — which
  is exactly the discipline this repo already enforces for the docs. There is also
  a newer experimental `@remotion/web-renderer` that encodes in-browser via
  WebCodecs, no Node server, if you want to avoid Lambda.

**Hyperframe is not a standard, verifiable tool** — I couldn't find a real
motion-design library by that name that runs in HTML, so I won't guess at its
API. If you meant something specific (a Framer feature, or a particular npm
package), point me at its docs and I'll give you an accurate answer instead of a
plausible one. Don't build on my say-so here.

**My honest recommendation for the time you have:** don't reach for Remotion to
animate the *live prototype*. The existing CSS/SVG animations (the stream-to-lump
collapse, the collections timeline, the distribution chart) already carry the
demo and cost nothing. Use Remotion only if you decide to produce the separate
submission video — and if you do, wire it to `FIGURES.json` so the two rules above
still hold. For in-app motion, plain CSS transitions and the Web Animations API
are lighter, need no build step, and keep the prototype a single file.

If you want the smoothest path: keep `prototype.html` as the live demo, and if
there's time, spin up a tiny separate `video/` Remotion project for the sizzle
reel. Two artifacts, cleanly separated, neither blocking the other.

## Things not to do

- Don't add a payouts flow through Pinch. It collects, it doesn't disburse.
  Advances and withdrawals are off-rail bank transfers — model them as a queued
  batch and say so.
- Don't attempt live compliance. Stay in test mode. Build the compliance-status
  panel against the three flags instead.
- Don't reintroduce "Grade A-" — ASIC has views on agency-style ratings. It's
  "Rail Score". `docs/07-regulatory.md`.
- Don't call subscription revenue a "receivable". It's contract/future revenue.
  That word choice produced v1's wrong loss model.

## First commands in the new session

```bash
python3 tools/check.py install-git-hooks   # once — git won't auto-enable hooks
python3 tools/check.py check               # confirm green baseline before editing
cd engine && python3 run.py && python3 stress.py   # see every number the model produces
```

Then open `docs/00-decisions.md` to see what's settled and what would reverse it,
and `docs/08-external-setup.md` to fire off the Pinch Slack message that unblocks
everything else.
