# Upfront marketplace app — design

Real, running product on top of the existing engine/integration/docs, for
hackathon submission tonight (2026-07-31). Turns the scripted `prototype.html`
demo into an actual app: a business can onboard, get underwritten, and open a
funding round; an investor can browse open rounds and invest — with live
Pinch API calls behind both, in test mode.

See [[hackathon_context]] for the deadline and judging philosophy this is
built against, and `docs/00-decisions.md` (D1, D9, D10) for the constraints
that shaped this design — one Pinch credential set, managed merchants only,
synthetic-but-calibrated books, test mode throughout.

## Why this shape

The core hackathon claim is "we underwrite real payment attempts, not a P&L
someone typed in." A generic "connect your Pinch account" button doesn't
prove that for a brand-new business — a fresh managed merchant has zero
payment history. So onboarding creates a **real** managed merchant via
`POST /merchants/managed`, then seeds it with a realistic payment history
calibrated to the business's own answers (cadence, ticket size, sector),
and the underwriting pull that follows is a live Pinch API call against that
seeded data, not a number computed in the app layer. This is the same
pattern `integration/seed_sandbox.py` already uses for Voltride, generalized
to run per-business at onboarding time instead of once for a fixed scenario.

## Architecture

**Backend**: Python + FastAPI, in `webapp/api/`. Imports `engine/` and
`integration/` directly — no duplicated pricing, risk, or Pinch logic.
SQLite for persistence (`webapp/api/upfront.db`). All Pinch calls are
server-side only, against `/test/`, using the existing `PinchClient`.

**Frontend**: React + Vite, in `webapp/frontend/`. Talks to the API over
`fetch`. Recharts for the investor-side outcome-distribution chart. Visual
language carried over from `prototype.html` rather than designed from
scratch.

**Session**: lightweight — name + email, no password. A random token stored
server-side (`sessions` table), returned as a cookie.

## Data model (SQLite)

```
businesses(id, name, email, sector, asset_class, mch_id, created_at)
deals(id, business_id, eligible_face_c, offer_c, rail_score,
      mean_return, p5_return, p1_return, prob_loss, fee_drag,
      target_c, raised_c, min_ticket_c, deadline_at, status, created_at)
investors(id, name, email, created_at)
investments(id, deal_id, investor_id, amount_c,
            pinch_payment_link_id, pinch_payment_link_url, created_at)
sessions(token, role, owner_id, created_at)
```

`status` on `deals`: `open` → `funded` (raised_c >= target_c) or `expired`
(deadline_at passed while still open).

## Business flow

1. **Start** — name + company email → session.
2. **Onboard ("Connect Pinch account")** — form: sector, asset class
   (contract revenue vs invoice — use exactly these terms, not
   "receivable," per the domain vocabulary rules in CLAUDE.md), typical
   ticket size, cadence, rough customer count. On submit:
   - `POST /merchants/managed` (real call) → store `mch_id`
   - seed 26 weeks of payment history calibrated to the answers (new
     module, see below). 26 weeks because the engine's WAL convention is
     already defined against a flat 26-week book (CLAUDE.md), so a
     different horizon would silently invalidate that figure.
   - `pull_book()` → `adapter.py` → `pricing_engine.py` (real call, real
     computation)
   - This takes several seconds. UI shows explicit stages: "connecting to
     Pinch" → "reading your book" → "pricing your risk" — not a bare
     spinner.
3. **Offer** — Rail Score, fee-drag panel, eligible face, cash offer
   (mirrors `prototype.html`'s analysis screen). Business then sets:
   - round deadline (24h / 3 days / 7 days / 14 days)
   - minimum investor ticket
   Submitting opens the `Deal` (`status=open`).
4. **Deal status** — funding progress bar, updates as investors commit,
   `funded` state once `raised_c >= target_c`.

## Investor flow

1. **Start** — name + email → session.
2. **Marketplace** — open deals: company/sector, Rail Score, **mean / 5th
   percentile / probability of loss shown together, always** (the same
   `claims` guard discipline the docs enforce applies to this UI, not just
   markdown), fee drag, funding progress, deadline.
3. **Deal detail** — book summary, cash-flow schedule, outcome distribution
   chart, invest form. Submitting:
   - server clamps amount to `min(requested, target_c - raised_c)`
   - wraps the raise-check + insert in a DB transaction (SQLite is
     single-writer; this is enough to prevent two investors overshooting
     the target)
   - `POST /payment-links` (real call, test mode) → store link id/url,
     record the `investment` row

## New code vs reused code

**Reused as-is**: `engine/pricing_engine.py`, `engine/fees.py`,
`engine/portfolio_risk.py`, `integration/pinch_client.py`,
`integration/adapter.py`.

**New**:
- `webapp/api/` — FastAPI app, routes, SQLite access layer
- `webapp/api/seeding.py` — parameterized version of
  `seed_sandbox.py`'s seeding logic, driven by onboarding answers instead
  of one fixed scenario. `seed_sandbox.py` itself is left alone as a
  standalone script.
- `webapp/frontend/` — React + Vite app

## Error handling

- Pinch call failure during onboarding → explicit error state with retry.
  Log the `mch_id` even on partial failure (e.g. merchant created but
  seeding failed) so it's traceable, never silently orphaned.
- Onboarding is submit-once: check for an existing `mch_id` on that
  business email before creating a second managed merchant.
- All money is integer cents end-to-end. Frontend converts dollars → cents
  before sending; backend rejects anything else, same discipline as the
  `money_type` guard already enforces in `engine/`.

## Testing

- Existing engine/integration test suite stays green, unchanged.
- New backend integration tests cover onboard → offer → deal → invest
  against a stubbed `PinchClient` (no live network in automated tests).
- Before the demo: one real, live smoke test against the actual Pinch test
  sandbox. Per the `pinch-api` skill's existing rule, this flow is not
  "done" until a real test-mode call returns the expected result — a
  passing stub test is not sufficient evidence on its own.

## Build order

1. Data model + parameterized seeding + live onboarding call — riskiest,
   most Pinch-dependent, proves the core claim first.
2. Business offer screen + deal creation.
3. Investor marketplace + deal detail + invest (payment link).
4. Wire the React frontend to all of the above, styled from
   `prototype.html`.

## Out of scope

- Real authentication (passwords, email verification).
- Webhook-driven funding updates (polling/refresh is enough for a demo).
- Recourse-debit and collections-side flows (already covered by the
  existing engine/`docs/09-demo.md` script) — this spec is additive, not a
  replacement for that scripted 60-second demo.
- Anything beyond Pinch test mode. No live compliance, no real money, per
  `docs/00-decisions.md` D10.
