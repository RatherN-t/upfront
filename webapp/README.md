# webapp — the running product

The marketplace, on top of the engine in `engine/` and the Pinch client in
`integration/`. No pricing, risk or fee logic lives here; if a number is
wrong it is wrong in `engine/`.

```
webapp/
  api/           FastAPI + SQLite
    main.py            routes, sessions
    db.py              schema and the one place with real concurrency
    pinch_gateway.py   live Pinch, or a labelled simulator
    underwriting.py    gateway JSON -> adapter -> engine -> distribution
    test_api.py        30 tests, no network
  frontend/      React + Vite
  seed_demo.py   reset to a known demo state
```

## Run it

Two terminals, from the repo root.

```bash
# once
python3 -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" httpx
(cd webapp/frontend && npm install)

# terminal 1 — API
cd webapp/api && ../../.venv/bin/python -m uvicorn main:app --port 8017

# terminal 2 — app
cd webapp/frontend && npm run dev
```

Then open **http://localhost:5173**. The Vite dev server proxies `/api` to
port 8017, which keeps the session cookie same-origin — pointing the browser
straight at the API instead will silently drop the session.

Port 8017 rather than 8000 because Docker Desktop commonly holds 8000.

```bash
.venv/bin/python webapp/seed_demo.py     # three businesses, rounds open
```

Run that before a rehearsal. It goes through the same HTTP endpoints a
browser does — there is no back door that writes deals directly, because a
seeding path that skips the real flow stops proving the real flow works.

## Live Pinch vs simulator

With `PINCH_APP_ID` and `PINCH_SECRET` set, the gateway makes real test-mode
API calls: a managed merchant per business, real payers with DDR agreements,
a Plan and Subscriptions, a real underwriting pull, and a real payment link
per investment. Without them it runs an in-process simulator that emits
Pinch-shaped JSON.

Force the simulator even with credentials present:

```bash
UPFRONT_FORCE_SIMULATED=1 ../../.venv/bin/python -m uvicorn main:app --port 8017
```

**The mode is shown in the UI, returned by `/api/health`, and stored against
every business and investment.** That is deliberate. The same adapter code
runs in both modes, so a green test suite is real evidence about the adapter
and no evidence at all about Pinch — only a live test-mode call proves that
half. See `docs/10-get-credentials-now.md`.

### Two things the live path cannot do, and why

**Settled history.** Pinch's test-mode settlement runs on its own batch, so a
freshly seeded account has a real forward book and no processed payments for
days — Time-Travel returns events but does not force settlement. When the
live pull comes back with no settled payments, the attempt history is
generated so the book is gradeable, and the response carries
`history_source: "synthesised"`, which the UI states plainly on the book
panel. Everything structural — merchant, payers, mandates, plan,
subscriptions, forward schedule — is whatever Pinch actually returned. **A
business that has genuinely been trading has its own history, so this branch
never fires for them.**

**Book size.** Live seeding creates `LIVE_SEED_PAYERS` (12) payers, not the
customer count the business enters, because every payment is one HTTP call
and a 120-customer book is ~700 calls and several minutes. So a live advance
is roughly a tenth of what the same answers produce in the simulator. For a
full-size marketplace walkthrough, use `UPFRONT_FORCE_SIMULATED=1`; use live
mode to show the integration is real.

## Tests

```bash
.venv/bin/python -m unittest discover -s webapp/api -p 'test_*.py'
python3 tools/check.py check      # engine figures, tests, guards
```

The API tests force the simulator regardless of ambient credentials, so they
never spend a real call and never depend on network.

## Known limitations

- **Sign-in is name + email with no password.** Anyone who knows a business's
  email can take its session. Acceptable only because everything is Pinch
  test mode; real auth is a prerequisite before this points anywhere near
  live credentials. Documented at the top of `main.py`.
- Funding progress updates on page load, not by webhook.
- Advances to businesses and payouts to investors are outside Pinch — it
  collects, it does not disburse.
