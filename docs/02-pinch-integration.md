# 02 — Pinch integration (exact API usage)

Every call this project makes, with real request and response shapes taken from
the Pinch OpenAPI reference. Endpoints and examples verified against
docs.getpinch.com.au. All amounts are **integer cents**. Send
`pinch-version: 2020.1` on every request.

Base URLs:

```
Test   https://api.getpinch.com.au/test/
Live   https://api.getpinch.com.au/live/
Auth   https://auth.getpinch.com.au/connect/token
```

Corrections to the original prototype, now guarded:

| Wrong (v1 site) | Right |
|---|---|
| `POST /merchants` | `POST /merchants/managed` |
| Merchant ID as `client_id` | **Deprecated.** Use an Application ID + Secret |
| `POST /plans/calculate` | `GET /plans/{id}/calculated-payments` |
| Fees ignored | Fees are an underwriting input — `engine/fees.py` |

---

## 0. Authentication — OAuth 2.0 client credentials

Merchant-ID auth is deprecated. Create an **Application** in the portal
(web.getpinch.com.au/api-keys) for an Application ID + Secret Key.

```http
POST https://auth.getpinch.com.au/connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=YOUR_APP_ID&client_secret=YOUR_SECRET
```

```json
{ "access_token": "eyJhbGci...", "expires_in": 3600, "token_type": "Bearer" }
```

Tokens last **1 hour**. Cache and reuse — do not fetch one per call. Then every
API request carries:

```http
Authorization: Bearer eyJhbGci...
pinch-version: 2020.1
```

---

## 1. Onboard a business as a managed merchant

`POST /merchants/managed` — Upfront's single credential set controls every
business created this way.

```http
POST https://api.getpinch.com.au/test/merchants/managed
Authorization: Bearer <token>
pinch-version: 2020.1
Content-Type: application/json

{
  "companyName": "Voltride Pty Ltd",
  "companyEmail": "ops@voltride.example",
  "bankAccountRoutingNumber": "000000",
  "bankAccountNumber": "000000000",
  "bankAccountName": "Upfront Collections — Voltride",
  "country": "AU",
  "contacts": [
    { "email": "founder@voltride.example", "firstName": "Dana",
      "lastName": "Reyes", "contactType": "owner", "isPrimaryContact": true }
  ],
  "ipAddress": "203.0.113.7",
  "userAgent": "Upfront/1.0"
}
```

Response (note `testOnlyMerchant` and the compliance gate):

```json
{
  "id": "mch_XXXXXXX",
  "testMerchantId": "mch_test_XXXXX",
  "testOnlyMerchant": true,
  "companyName": "Voltride Pty Ltd",
  "bankAccountRoutingNumber": "000000",
  "compliance": {
    "status": "new",
    "liveEnabled": false,
    "transactionsEnabled": false,
    "settlementsEnabled": false
  },
  "contacts": [ { "id": "con_XXXX", "contactType": "owner", "isPrimaryContact": true } ]
}
```

Save `id` (the `mch_`). Build the compliance panel on the three booleans — all
false at creation, and staying in test mode is fine for the hackathon.

**`bankAccountName` / routing / number is the disbursement account.** Setting it
to an Upfront-controlled collections account is the lockbox that makes the whole
model work (`docs/01-architecture.md`).

---

## 2. Act as that merchant

Add one header to any call and you are operating their account with your own
credentials:

```http
Current-Merchant: mch_XXXXXXXXXXXXXXXX
```

Omit it and the call executes against **Upfront's own** merchant instead. This
is the highest-severity bug class in the codebase, which is why the client
(`integration/pinch_client.py`) makes the header structurally required for any
per-merchant call.

---

## 3. Read the book (underwriting pull)

All with `Current-Merchant` set.

```http
GET /payers?page=1                          # customers, paged
GET /plans                                  # contract templates
GET /subscriptions                          # active contracts
GET /plans/{id}/calculated-payments?startDate=2026-08-01&totalAmount=...
GET /payments/processed?page=1              # dishonour history, paged
GET /transfers                              # settlements
GET /transfers/items/{id}                   # settlement line items
```

`GET /plans/{id}/calculated-payments` returns the computed forward schedule
(dates + amounts) — this **is** the cashflow the engine discounts.
`GET /payments/processed` (paged) is the attempt history the bad-debt scanner reads.

---

## 4. Create a payer (a customer of the business)

`POST /payers`. Required: `firstName`, `emailAddress`. Attach a source inline.

```http
POST /payers
Current-Merchant: mch_XXXX
pinch-version: 2020.1

{
  "firstName": "Fred", "lastName": "Hamburger",
  "emailAddress": "fred@mailinator.com", "mobileNumber": "0400123456",
  "source": { "sourceType": "bank-account", "token": "tkn_..." },
  "metadata": "{\"upfront\":{\"deal_id\":\"dl_2026_0729_voltride\"}}"
}
```

Response includes `id` (`pyr_...`), the `sources[]` with `src_` ids, and any
`agreements[]` (the direct-debit authorisation, `agr_`, `status: active`).

Bank-account and card details must be tokenised client-side with **Pinch
CaptureJS** so raw details never hit your server — you pass the resulting
`tkn_...`, never a PAN or BSB/account.

---

## 5. Schedule a payment / collect

`POST /payments`. Required: `payerId`, `amount` (cents), `transactionDate`.

```http
POST /payments
Current-Merchant: mch_XXXX
pinch-version: 2020.1

{
  "payerId": "pyr_dLCdmrOmXKwuWH",
  "amount": 3478,
  "transactionDate": "2026-08-05",
  "description": "Voltride wk5 subscription",
  "nonce": ["voltride-pyr_dLC-wk5-2026-08-05"],
  "applicationFee": 50
}
```

Two fields that matter to this project:

- **`nonce`** — one-time reference. Send the same nonce twice and Pinch returns
  the existing payment (HTTP 403 "Nonce Replay") instead of double-charging.
  Non-negotiable on every retry and recourse debit.
- **`applicationFee`** (cents, **managed merchants only**) — an extra fee that
  goes to the parent merchant (Upfront). **This is the clean way to take our
  cut in-flight** and resolves the open architecture question: we do not need a
  separate lockbox mechanism to earn, though we still route settlement to a
  collections account. Confirmed present in the `POST /payments` schema.

Response carries `id` (`pmt_`), `attemptId` (`att_`), `status` (`scheduled`),
`totalFee`, `applicationFee`, `estimatedTransferDate`, and a full `attempts[]`
array with per-attempt `fees` (`transactionFee`, `applicationFee`, `taxRate`).

---

## 6. Collect results (events + webhooks)

Direct debit is processed overnight and takes days. Two ways to learn the result:

**Poll** `GET /events` and read `type`:

- `bank-results` — a batch of failed payments (match `pmt_` ids you saved)
- `transfer` — a settlement occurred; get the `tra_` id, then
  `GET /transfers/items/{id}` for line items (`type: Settlement` or `Dishonour`)

**Or webhooks** `POST /webhooks` per merchant. Every delivery carries a
`pinch-signature` header (timestamp + HMAC). Verify before parsing, check clock
skew (5 min default), idempotent on `evt_` id.

Non-negotiables:

1. Idempotent on `evt_` id — events arrive twice.
2. Settlement is reversible — a payment can settle then reverse days later.
   Model each week as a state machine, never a boolean.
3. Never trust the body before verifying the signature.

---

## 7. Retry vs recourse

Soft dishonours retry with a fresh `POST /payments` (+ nonce). Hard ones never do.

| Code | Retry? |
|---|---|
| `insufficient-funds`, `temporary-problem`, `technical-error` | Yes |
| `blocked-by-bank`, `invalid-card`, `invalid-account`, `unsupported-card` | No |

Retrying a hard code burns a $5 decline fee and cannot succeed. On a hard
failure, skip to recourse: `POST /payments` against the **business's own**
recourse Payer record in Upfront's master account.

---

## 8. Investor money in

Investor is a Payer of **Upfront's own** merchant (no `Current-Merchant`).
Simplest: `POST /payment-links` → hosted checkout URL → redirect back with
`paymentLinkId` and `paymentId`. Zero PCI surface. Card in-app is
`POST /payments/realtime` with a CaptureJS `tkn_`.

Money out is an off-rail bank transfer. Pinch collects; it does not disburse.

---

## 9. Testing — this is how you make it real without real money

Pinch issues **two separate credential sets** under one Application — Live
Keys (`app_...` / `sk_live_...`) and Development Keys (`app_test_...` /
`sk_test_...`). Test mode means the Development pair against the `/test/`
base URL, not the same credentials as live. Mixing a Live Application ID with
a test Secret Key returns `400 {"error":"invalid_client"}` — we hit exactly
this. `PinchClient` now refuses `sk_live_` secrets, refuses `live=True`, and
detects the mismatched-pair case by name (docs/00-decisions.md D10).
No separate sandbox login, no public list of demo merchants.
[source: web.getpinch.com.au/api-keys, observed 2026-07-31]

### Test cards (any future expiry, any CVC)

| Number | Type | Country |
|---|---|---|
| `4242424242424242` | Visa | AU |
| `4000000360000006` | Visa | AU |
| `378282246310005` | AMEX | AU |
| `5555555555554444` | Mastercard | USA |

### Test bank accounts

Any BSB/account is accepted in test mode. Provided for convenience:
`000-000 / 0000000000` and `000-001 / 1234567890`.

### Force specific failures

Put a dishonour code, prefixed with `#`, anywhere in `description` or the payer
`firstName`:

```
description: "Voltride wk5 subscription #insufficient-funds"
description: "Voltride wk5 subscription #blocked-by-bank"
```

### Time Travel — the feature that makes end-to-end testing instant

Direct debit normally takes days. Add a header to fast-forward:

```http
Time-Travel: 2026-08-02T09:45:59Z
```

Full end-to-end in one sitting:

1. Create a payer with a test bank account.
2. Schedule a payment for today.
3. Re-request with `Time-Travel` set to the next morning → payment processes,
   `bank-results` event fires.
4. Advance further → `transfer` event fires, settlement lands.

**Remove `Time-Travel` before go-live.** It is ignored in live mode but should
not be shipped.

There is no public list of pre-made demo merchant accounts — you create your own
managed merchants under your Application, and every one is `testOnlyMerchant`
until compliance is passed. See `docs/08-external-setup.md`.
