# 08 — What you must do outside this repo

Answering the direct question: **yes, there are things only you can do, and one
of them is on the critical path.** Do that one today.

---

## 1. Pinch account and API credentials — 15 minutes

Sign up at getpinch.com.au. Your Merchant account is created on signup. Then in
the Pinch Portal, under **API Keys**, create an application. That gives you an
**Application ID** and a **Secret Key**, which you exchange for an OAuth 2.0
access token. The .NET SDK handles token acquisition for you; if you are not on
.NET you are calling the token endpoint yourself.

Environments:

```
Test    https://api.getpinch.com.au/test/
Live    https://api.getpinch.com.au/live/
```

Send `pinch-version: 2020.1` on every request. It is technically optional, and
omitting it means you silently ride the latest version and inherit breaking
changes mid-demo.

**Never commit the secret key.** The `no_secrets` guard will catch `sk_live_`,
`sk_test_` and `whsec_` patterns, but it only runs on files you actually add.

---

## 2. Managed-merchant access — THE CRITICAL PATH ITEM

The Managed Merchants Payments Guide opens with: *"To make use of these features
you will require a verified Pinch Developer account."*

Your entire architecture depends on `POST /merchants/managed` and the
`Current-Merchant` header. If your sandbox account is not enabled for managed
merchants, none of it works, and you will not discover that at 9pm on Thursday
in a good mood.

**Ask on Slack today.** Exact message:

> We're building a receivables-financing platform on Pinch for the hackathon.
> Our whole model is master-merchant + managed merchants with the
> `Current-Merchant` header. Three things we need to confirm:
>
> 1. Can you enable managed-merchant access on our sandbox application so we can
>    call `POST /merchants/managed` and act as a sub-merchant?
> 2. Can the master merchant set, and later change, a managed merchant's
>    disbursement bank account? We need settlements to route to a platform
>    collections account rather than the business's own account.
> 3. The Transfer object mentions "application fees — any additional fees charged
>    on the platform". Is there a documented way for a master merchant to take a
>    per-payment application fee? If so that's cleaner than the collections
>    account and we'd rather build it that way.

Questions 2 and 3 are architecture-deciding. See `01-architecture.md`.

---

## 3. A publicly reachable webhook endpoint

Pinch pushes events to a URL you register via `POST /webhooks`. Localhost will
not do. Use a tunnel during the build:

```bash
ngrok http 8000          # or cloudflared tunnel --url http://localhost:8000
```

Register one webhook **per managed merchant** — the payments guide is explicit
that you should create the subscription immediately after storing the merchant
id. Subscribe to at least: `bank-results`, `realtime-payment`,
`scheduled-process`, `transfer`, `payment-created`, `dispute-created`.

Store the returned `whsec_...` secret in your environment, never in the repo.
Every delivery carries a `pinch-signature` header with a timestamp and HMAC.
Verify it before touching the body, and check clock skew — the SDK default
tolerance is five minutes.

---

## 4. Tokenisation for any real card entry

If you build your own payment form rather than using hosted Payment Links, card
details must be tokenised client-side with **Pinch CaptureJS** so raw PANs never
reach your server. There is a working credit-card tokenisation JSFiddle linked
from the CaptureJS docs. You then pass the `tkn_...` to
`POST /payments/realtime`.

For the hackathon, **use Payment Links instead.** `POST /payment-links` returns a
hosted checkout URL, the customer pays on Pinch's page, and you get back
`paymentLinkId` and `paymentId` on the return redirect. Zero frontend payment
work and zero PCI surface.

---

## 5. Seeding realistic failures in the sandbox

You do not need fake JSON. Sandbox lets you force any dishonour code by putting
it, prefixed with a hash, into the payment description or the payer's first name:

```
description: "Voltride wk5 subscription #insufficient-funds"
description: "Voltride wk5 subscription #blocked-by-bank"
```

That runs a real payment through the real sandbox, produces a real dishonour, and
fires your real webhook handler. It is the difference between a demo that looks
built and one that is built.

---

## 6. Compliance, only if you go anywhere near live

A managed merchant's `compliance` object returns three booleans — `liveEnabled`,
`transactionsEnabled`, `settlementsEnabled` — all false at creation. Moving them
requires identity and proof-of-business documents via `POST /documents`, or
manual onboarding through the Connected Merchants tab in the portal.

**For the hackathon, stay in test mode.** Do not attempt live compliance. Build
the compliance-status screen against those three flags instead — it demonstrates
you understand the gate without needing to pass through it.

---

## 6b. Example / test accounts — how to get them

There is **no public list of ready-made demo merchant accounts.** Pinch test
mode isn't a separate sandbox with shared logins — it runs on your own
credentials against the `/test/` base URL. So the way you get "an account to
test with" is to create one:

1. Get your own Application ID + Secret (step 1 above). Free.
2. Run `python3 integration/seed_sandbox.py`. It creates a managed merchant
   under you, seeds ~130 real test payments (mostly settling, some
   `#insufficient-funds` that cure, some `#blocked-by-bank` that don't),
   Time-Travels past the processing window so results actually post, and then
   prices the resulting book with the engine.
3. That merchant is `testOnlyMerchant: true` and needs no compliance. Re-price
   it any time without reseeding.

Test cards (e.g. `4242424242424242`, any future expiry/CVC) and test bank
accounts (any BSB/account is accepted; `000-000 / 0000000000` for convenience)
are in `docs/02-pinch-integration.md` §9.

The two architecture questions from §2.3 are now **partly answered by the docs
themselves**: `POST /payments` accepts an `applicationFee` (cents, managed
merchants only) that goes to the parent merchant — confirmed in the payment
schema — so Upfront can take its cut in-flight. You still want to confirm with a
mentor that the managed merchant's disbursement account can be set/changed to an
Upfront collections account, which is the settlement side of the same design.

## 7. Things you do NOT need

- **A payouts rail.** Pinch collects; it does not disburse arbitrary payments.
  Advances to businesses and withdrawals to investors are ordinary bank
  transfers, outside Pinch. Model them as a queued payout batch in the UI and say
  so on stage rather than faking it.
- **An AFSL.** Not for a prototype with no real money. See `07-regulatory.md` for
  what would be required if this ever went live.
- **A real trust account.** Same reasoning. Name it in the architecture, do not
  open one.

---

## Setup checklist

```
[ ] Pinch account created, application created, App ID + Secret Key stored in env
[ ] pinch-version header set on every call
[ ] MANAGED MERCHANT ACCESS REQUESTED ON SLACK          <- do this first
[ ] Disbursement-account question asked                  <- architecture-deciding
[ ] Application-fee question asked                       <- architecture-deciding
[ ] Tunnel running, webhook registered per merchant, whsec_ in env
[ ] Signature verification implemented and tested with a bad signature
[ ] Sandbox seeded with #insufficient-funds and #blocked-by-bank payments
[ ] tools/check.py check passes
[ ] .githooks installed:  python3 tools/check.py install-git-hooks
```
