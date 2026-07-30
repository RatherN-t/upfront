---
name: pinch-call
description: Write or review a call against the Pinch Payments API. Use when adding an endpoint, a webhook handler, or a managed-merchant operation, or when a Pinch call is behaving unexpectedly.
---

Write or review the Pinch call for `target`, `$ARGUMENTS`, or the endpoint under discussion.

Read `docs/02-pinch-integration.md` first. It records the endpoints this project actually uses and the ones that have already been documented wrongly.

Non-negotiables for every call. Send the `pinch-version` header; omitting it silently opts you into the latest version and future breaking changes. Send `Current-Merchant: mch_...` on every call made on behalf of a funded business, and never on calls against Upfront's own merchant. Use the test base URL until someone explicitly decides otherwise. Amounts are integer cents.

For anything that moves money, send a `Nonce`. Retrying a payment without one is how you double-charge a customer during a demo. The same applies to refunds.

For webhook handlers: verify the `pinch-signature` header before doing anything with the body, key idempotency off the `evt_` id, and design the handler so a payment can settle and then reverse days later. Direct debit results are batched and arrive with a one to three day lag, so a boolean `collected` flag is wrong; model the week as a state machine.

Distinguish soft dishonours that should retry from hard ones that must not. `insufficient-funds`, `temporary-problem` and `technical-error` are retryable. `blocked-by-bank`, `invalid-card`, `invalid-account` and `unsupported-card` are not, and retrying them burns a five dollar decline fee for nothing.

When testing, seed realistic failures by putting the dishonour code prefixed with a hash into the payment description or the payer first name in sandbox.

Final: the call, the headers, the idempotency story, and the failure branch you handled.
