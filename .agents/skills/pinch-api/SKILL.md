---
name: pinch-api
description: Handle anything involving the Pinch Payments API — authenticating, creating managed merchants, reading a business's book, scheduling or retrying payments, taking application fees, verifying webhooks, and testing with Time-Travel and dishonour codes. Use whenever a task touches Pinch endpoints, the pinch_client, the adapter, or sandbox seeding.
---

Handle the Pinch work for `target`, `$ARGUMENTS`, or the endpoint under discussion.

Read `docs/02-pinch-integration.md` first — it has the exact request and response shapes, verified against the Pinch OpenAPI reference. Use `integration/pinch_client.py` rather than raw HTTP; it exists so the invariants below cannot be violated by accident. If a call is missing from the client, add it there, not inline.

## Authentication

Auth is OAuth 2.0 client credentials against `https://auth.getpinch.com.au/connect/token`, exchanging an Application ID and Secret for a Bearer token that lasts one hour. Merchant-ID auth is deprecated and must not be used. Tokens are cached in the client until sixty seconds before expiry; never fetch one per call. Credentials come from environment variables `PINCH_APP_ID` and `PINCH_SECRET`, never hardcoded and never committed. The `no_secrets` guard fails the build on `sk_`, `whsec_` and bearer patterns.

## The one rule that prevents the worst bug

A call made on behalf of a financed business needs the `Current-Merchant: mch_...` header. A call that omits it executes against Upfront's own account instead, silently. The client makes this structural: `client.as_merchant(mch_id)` returns a scope whose every method sends the header, and the base client exposes no per-merchant reads at all. Never reintroduce a raw per-merchant request that takes the merchant id as a plain argument — route it through `as_merchant`.

## Money is integer cents

Every amount crossing the API boundary is an integer number of cents. The client's `_cents()` helper raises on a float or a bool. The `money_type` guard rejects float money in the engine. A dollar value anywhere near an API call is a bug.

## Idempotency and retries

Every money-moving call carries a `nonce`. Sending the same nonce twice makes Pinch return the existing payment (HTTP 403 with a `pmt_` body, which the client treats as success, not an error) instead of creating a duplicate. This is what stops a retry from double-charging a customer. Soft dishonours — `insufficient-funds`, `temporary-problem`, `technical-error` — may be retried with a fresh payment and a new nonce. Hard dishonours — `blocked-by-bank`, `invalid-card`, `invalid-account`, `unsupported-card` — must not be retried; each retry burns a five dollar decline fee and cannot succeed. On a hard failure, go to recourse: a payment against the business's own recourse payer in Upfront's master account.

## Application fees are how Upfront earns in-flight

`POST /payments` accepts an `applicationFee` in cents for managed merchants, and it goes to the parent merchant. This is the clean mechanism for taking Upfront's cut without a separate settlement-splitting step, and it is confirmed present in the payment schema. Settlement still routes to an Upfront collections account via the managed merchant's disbursement bank details, set at creation.

## Webhooks

Register one webhook per managed merchant, right after storing the `mch_` id. Every delivery carries a `pinch-signature` header with a timestamp and HMAC. Verify the signature before parsing the body, check clock skew against the five-minute default, and key idempotency off the `evt_` id because events arrive more than once. Model each scheduled week as a state machine, not a boolean, because a direct-debit payment can settle and then reverse days later when bank results post.

## Reading a book

The underwriting pull is `get_payers`, `get_plans`, `get_subscriptions`, `calculated_payments` per plan, `get_processed_payments`, and `get_transfers`, all through a merchant scope. `MerchantScope.pull_book()` does this in one call. `integration/adapter.py` maps the raw JSON into engine `Book`, `Attempt` and `Receivable` objects so the same pricing and risk code runs on live data and on mocks. When a Pinch field changes, fix the adapter, not the engine.

## Testing without real money

Test and live are **separate credential pairs** under one Application — Live Keys (`app_...` / `sk_live_...`) and Development Keys (`app_test_...` / `sk_test_...`), from `web.getpinch.com.au/api-keys` — used against separate base URLs, `https://api.getpinch.com.au/test/` versus `/live/`. Mixing a Live Application ID with a test Secret Key gets a bare `400 {"error":"invalid_client"}`. `PinchClient.from_env` refuses `sk_live_` secrets, refuses `live=True`, and names the mismatched-pair case instead of leaving you to decode the 400 (docs/00-decisions.md D10). There is no separate sandbox login and no public demo merchant — you create your own managed merchant, which is `testOnlyMerchant` until compliance passes.
[source: web.getpinch.com.au/api-keys, observed 2026-07-31] Force a specific failure by putting a dishonour code prefixed with a hash into the payment `description` or the payer `firstName`, for example `#insufficient-funds`. Use the `Time-Travel` header, an ISO datetime, to fast-forward past the overnight processing and settlement windows so an end-to-end direct-debit flow runs in one sitting instead of several days. The client refuses to send `Time-Travel` in live mode. Test cards and test bank accounts are listed in `docs/02-pinch-integration.md`; any BSB and account number are accepted in test mode. `integration/seed_sandbox.py` creates a full evaluable book end-to-end.

## Before reporting done

State which calls you made, the idempotency story for anything that moved money, the failure branch you handled, and whether you tested against test mode with Time-Travel or only wrote code. Do not claim a flow works end-to-end unless a real test-mode call returned the expected event.
