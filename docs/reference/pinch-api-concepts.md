# Pinch API core concepts (source reference)

Verbatim reference material from the Pinch API docs
(docs.getpinch.com.au/docs/pinch-payments-api-core-concepts), kept here so
`docs/02-pinch-integration.md` and `integration/` can be checked against it
without re-fetching. If the two ever disagree, `02-pinch-integration.md` wins
for anything already verified against a live response shape — update this
file, don't hand-edit that one to match.

Cross-checked against this repo on 2026-07-31: `integration/adapter.py`
already uses the exact payment-status vocabulary below (`scheduled`,
`processing`, `approved`, `dishonoured`, `settled`, `cancelled`), and the
Agreement (DDR) auto-creation on a bank-account source matches
`docs/02-pinch-integration.md`. **Refund** and **Surcharge**, both described
below, are not implemented anywhere in this repo — not required for the
current demo flow.

---

## How the pieces fit together

```
┌─────────────┐       owns        ┌────────────┐
│  Merchant   │──────────────────▶│   Payer    │
└─────────────┘                   └─────┬──────┘
                                        │ has
                              ┌─────────┼──────────┐
                              ▼         ▼          ▼
                        ┌─────────┐ ┌─────────┐  ┌───────────┐
                        │ Source  │ │Agreement│  │Subscription│
                        └────┬────┘ └─────────┘  └─────┬─────┘
                             │                         │ created from
                             │                    ┌────▼────┐
                             │                    │  Plan   │
                             │                    └─────────┘
                             │
                 charged via │
                        ┌────▼─────┐      settles into     ┌──────────┐
                        │ Payment  │──────────────────────▶│ Transfer │
                        └────┬─────┘                       └──────────┘
                             │ contains
                        ┌────▼─────┐
                        │ Attempt  │
                        └──────────┘
```

## Entities

**Merchant** — you, the business collecting payments. Authenticates via
Application ID + Secret. Can create **Managed Merchants**, sub-accounts the
parent fully controls — the foundation Upfront is built on.

**Payer** — a person or business you collect from. Owns `sources[]` and
`agreements[]`. Supports free-text `metadata`.

**Source** — a payment method on a Payer: `bank-account` (BSB + account) or
`credit-card`, tokenised client-side via Pinch CaptureJS so raw details never
hit your server.

**Agreement** — the formal Direct Debit Request (DDR) authorisation, required
under Australian banking rules for any bank-account payment. Lifecycle:
created → authorised (payer confirms, triggers a DDR/Service Agreement PDF
email) → cancelled (blocks future payments). Created automatically when a
bank-account source is attached to a payer.

**Payment** — the central entity: a request to collect money. Two modes:
*scheduled* (`POST /payments`, future `transactionDate`, editable/deletable
before processing) and *realtime* (`POST /payments/realtime`, card-only,
immediate, can create the payer inline). Statuses: `scheduled` → `processing`
→ `approved` | `dishonoured` → `settled` | `cancelled`. `Nonce` on both modes
makes a replayed request return the existing payment instead of duplicating.

**Attempt** — one execution try within a Payment. A Payment can have several
Attempts (retry after dishonour) but at most one successful Attempt. Each
carries its own amount, transaction date, status, source, dishonour detail,
settlement detail, and fee breakdown. The Payment's `attemptId` always points
at the current Attempt — this is how you tell a payment has been retried.

**Plan** — a reusable schedule template: free periods, fixed payments
(amount or % of total), recurring payments (frequency, offset, end
condition). Percentage-based plans set `requiresTotalAmount = true`. A Plan
can only be edited while it has zero active subscriptions.

**Subscription** — binds a Plan to a Payer, generating the actual dated
Payment records.

**Transfer** — the settlement batch: summary of settlements, dishonours,
refunds, application fees, processing fees, tax. Drill into line items for
the individual debits/credits.

**Refund** — returns money from a settled Payment, full or partial, also
nonce-protected. *Not used in this repo.*

**Event** — fired on anything noteworthy; the basis for both polling and
webhooks. Full type list below.

**Webhook** — subscribes to Events, pushed to your server. Every delivery
carries a `pinch-signature` header (timestamp + HMAC); verify before parsing,
check clock skew (5 min default).

## Payment statuses

| Status | Meaning |
|---|---|
| `scheduled` | Queued for future processing |
| `processing` | Currently being processed by the payment network |
| `approved` | Successfully collected |
| `dishonoured` | Initially processed but later failed (e.g. insufficient funds) |
| `settled` | Funds have been settled to the merchant's bank account |
| `cancelled` | Payment was cancelled before processing |

## Event types

| Event Type | Trigger |
|---|---|
| `payment-created` | A new payment is created |
| `bank-results` | Bank results received for direct debit payments |
| `realtime-payment` | A realtime (credit card) payment completes |
| `scheduled-process` | Scheduled payments are processed |
| `transfer` | A transfer/settlement occurs |
| `payer-created` | A new payer is created |
| `payer-updated` | A payer's details are updated |
| `refund-created` | A refund is created |
| `refund-updated` | A refund's status changes |
| `subscription-created` | A new subscription is created |
| `subscription-complete` | A subscription finishes all payments |
| `subscription-cancelled` | A subscription is cancelled |
| `dispute-created` | A payment dispute (chargeback) is raised |

Upfront currently reads `bank-results` and `transfer` (see
`docs/02-pinch-integration.md` §6). The rest are available but unused.

## Cross-cutting

- **Cents everywhere.** `$10.00` is `1000`.
- **`pinch-version: 2020.1`** on every request — technically optional, but
  omitting it means silently riding the latest version.
- **Pagination** via `totalPages` / `currentPage`; walk pages explicitly
  rather than an auto-paginate-all helper on large datasets.
- **Metadata** — free JSON on Payer, Payment, Plan, Subscription.
- **Surcharge** — pass processing fees to the payer for specific source
  types (`["bank-account", "credit-card"]`) on Payment/Subscription creation.
  *Not used in this repo.*
