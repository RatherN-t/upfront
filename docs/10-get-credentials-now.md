# 10 — Get credentials now (runbook)

Do this before anything else tonight. Everything in `webapp/` runs against a
simulator until these exist, and the simulator is not the demo you want to
submit. `docs/08-external-setup.md` covers the wider setup strategy; this is
just the ordered click-path plus what to do when it doesn't work.

**Answer to "can I test for free": yes.** The Pinch docs describe a *"free
Pinch Developer Account"* giving *"access to the Developer Portal and a
sandbox environment where you can test without processing real payments,"*
and state *"most developers are making test API calls within 15 minutes."*
Test mode is not a separate login — it is the same credentials against the
`/test/` base URL.
[source: docs.getpinch.com.au/docs/get-started-with-the-pinch-api]

---

## Steps

1. **Register a free developer account** at getpinch.com.au (portal:
   web.getpinch.com.au). This creates your Merchant account.

2. **Create an application** — portal → **API Keys** → create application.
   You get an **Application ID**, a **Secret Key**, and a Publishable Key.
   The Secret is shown once; store it immediately.

3. **Export them** in the shell you run the app from:

   ```bash
   export PINCH_APP_ID=...
   export PINCH_SECRET=...
   ```

   Never commit these. The `no_secrets` guard catches `sk_`, `whsec_` and
   bearer patterns, but only on files you actually add — it is a backstop,
   not a permission slip.

4. **Verify the token exchange works** (~10 seconds, no side effects):

   ```bash
   python3 -c "
   from integration.pinch_client import PinchClient
   pc = PinchClient.from_env(live=False)
   print('token ok:', bool(pc._ensure_token()))
   "
   ```

   A `PinchError 400/401` here means the credentials are wrong or the
   application was not created. Nothing else is worth debugging until this
   prints `token ok: True`.

5. **Verify managed-merchant access** — this is the one that can block the
   architecture:

   ```bash
   python3 integration/seed_sandbox.py
   ```

   Expected: a managed merchant is created (`mch_...`, `testOnlyMerchant:
   true`), test payments seed, and the engine prices the resulting book.

---

## If step 5 fails with 401/403 on `POST /merchants/managed`

This is the known risk, and it is architecture-deciding (`docs/00-decisions.md`
D1). The Managed Merchants Payments Guide states *"To follow this guide you'll
need a verified Pinch Developer account,"* and the docs **do not say** whether
"verified" gates managed-merchant creation in test mode.
[source: docs.getpinch.com.au/docs/managed-merchants-payments-guide]

Evidence it should work in test mode: the `POST /merchants/managed` response
schema returns `testOnlyMerchant: true` and a `compliance` block with all
three flags false — a shape that only makes sense if unverified test-mode
managed merchants are normal. That is inference, not confirmation.

**Do not spend an hour debugging this.** Ask on the hackathon Slack — the
exact message is already drafted in `docs/08-external-setup.md` §2, and it
bundles the two other architecture-deciding questions. Mentors are available
specifically for this.

---

## Fallback if managed merchants stay blocked

`webapp/` runs against a `PinchClient` that has two modes:

- **live** — real API calls, used whenever `PINCH_APP_ID` / `PINCH_SECRET`
  are present and managed-merchant access works.
- **simulator** — an in-process fake that mimics Pinch response shapes so
  the product is demonstrable with no credentials at all.

**The running mode is displayed in the UI and logged on every call.** This is
deliberate and must not be softened. A demo that claims live Pinch
integration while quietly running a simulator is the single fastest way to
lose credibility under a judge's question, and the honest version — "here is
the real integration, here is the simulator we built so it degrades
gracefully" — is a better answer anyway.

If it comes to that, the pitch shifts from "watch it hit Pinch live" to
"the integration is real and here is the code path; we ran it against the
sandbox at <time>" — which is why step 5 is worth doing early, even if you
demo from a seeded book later.
