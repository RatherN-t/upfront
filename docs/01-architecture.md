# 01 — Architecture

## The entity model

Upfront holds **one** set of Pinch credentials. Every financed business becomes a
**managed merchant** underneath it, and Upfront acts as that business by sending
one header.

```
              UPFRONT  (master merchant, one Application ID + Secret Key)
                   |
   +---------------+---------------+------------------+
   |               |               |                  |
 Voltride      Northline       Studio 04          INVESTORS
 mch_v...      mch_n...        mch_s...       (Payers of Upfront's
   |                                           own merchant account)
 Payers -- Sources -- Agreements (DDR)
   |
 Plans -> Subscriptions -> Payments -> Attempts
                              |
                          Transfers --> Upfront collections account
```

The docs are explicit: once a managed merchant is created, save the Merchant ID
and use it with the `Current-Merchant` header to call the API on their behalf
using your existing credentials.

Consequences worth stating plainly:

- **Customers never re-authorise anything.** Their mandate stays where it was and
  the debit still shows the business's name.
- **You inherit their entire payment history** as underwriting data.
- **You are operating someone else's merchant account.** Every call needs the
  header, and a call that omits it silently executes against Upfront's own
  account instead. That is the highest-severity bug class in this codebase.

---

## Where the money actually lands

This is the decision the whole model rests on, and it is not obvious from the
marketing pages.

Pinch settles Transfers **to the merchant's bank account** — and for a managed
merchant, that is the disbursement account on *its own* record
(`bankAccountRoutingNumber` + `bankAccountNumber`, both required at creation).
Collections do **not** automatically arrive at Upfront.

### Option A — collections account (assume this)

Set the managed merchant's disbursement account to an **Upfront-controlled
collections account**. This is the classic factoring lockbox. Every Transfer for
that `mch_` lands with Upfront, already net of dishonours and Pinch fees, and the
platform ledger splits it:

```
Transfer arrives
  |-- investor principal + yield share  -> investor ledger
  |-- Upfront servicing fee             -> platform revenue
  +-- surplus above funded schedule     -> swept back to the business
```

In production this must be a **segregated client-money trust account**, not an
operating account.

### Option B — application fees

The Transfer object includes "application fees — any additional fees charged on
the platform". If Pinch exposes a per-payment application fee to master
merchants, that is cleaner: money flows to the business as normal and Upfront
takes its cut in-flight. It is not in the public reference.

**Both questions are on the Slack list in `08-external-setup.md`. Ask before you
build.** Option A is the safe default and needs no undocumented behaviour.

---

## Recourse — the mechanism, not the badge

"If a payment fails it comes back to you" is a claim, not a design. The mechanism
is pure Pinch:

> At funding, the business signs a **direct-debit Agreement to Upfront**. It
> becomes a **Payer** in Upfront's own merchant account with a stored bank-account
> Source and an authorised DDR. Recourse is then just `POST /payments`.

Three tiers, in order:

1. **Net off future surplus.** A dishonour reduces the surplus otherwise swept
   back to the business. Costs nothing, handles most cases.
2. **Debit the recourse mandate** for any shortfall against the funded schedule.
   Send a `Nonce`.
3. **That dishonours too** — the business is in trouble. This is the only path
   that reaches an investor.

### What recourse is actually worth

Not much, in the case that matters. When the business is insolvent you are an
unsecured creditor behind employees and the ATO. The engine models recovery at
**20% unsecured** and **45% with a PPSR registration** over the purchased
receivables. Registering PPSR is the cheapest risk reduction available and should
be in the funding flow.

And the deeper problem, from `05-honest-returns.md`: for subscription books, the
receivable itself mostly evaporates on business failure because the service stops.
Recourse against an insolvent business over a stream that no longer exists is
thin protection. Say so.

---

## Two asset classes, deliberately different

| | Contract (subscription) | Invoice (B2B) |
|---|---|---|
| What it is | Service not yet delivered | Work already delivered |
| Survives business failure | 15% | 75% |
| Loss given default | 47% | 14% |
| Typical ticket | $16–$65 | $18,000 |
| Pinch fee drag | 2.4%–4.4% | 0.04% |
| Forward schedule | Native, via `/plans/{id}/calculated-payments` | Your own invoice table |
| Legal character | Closer to revenue-based financing | Genuine factoring |

The engine treats `asset_class` as a first-class input. Two books with the same
revenue and the same bad-debt rate are not the same credit, and the model has to
know which is which.

---

## Data flow

```
1. Onboard    POST /merchants/managed -> mch_
              POST /documents            KYB
              POST /webhooks             per merchant

2. Read       Current-Merchant: mch_
              GET /payers, /plans, /subscriptions
              GET /plans/{id}/calculated-payments   forward schedule
              GET /payments/processed  (paged)      dishonour history

3. Underwrite engine/pricing_engine.py
              scan -> screen -> fee drag -> grade -> price

4. Fund in    POST /payment-links   (Upfront's merchant, investor pays)
5. Fund out   bank transfer, off-rail

6. Collect    webhooks: bank-results, realtime-payment, scheduled-process,
                        transfer, dispute-created
              POST /payments  retries, with Nonce

7. Recourse   POST /payments against the business's own recourse Payer

8. Settle     GET /transfers, GET /transfers/items/{id}
```

---

## Failure modes the design has to survive

| Failure | Design response |
|---|---|
| Webhook delivered twice | Idempotency keyed on `evt_` id |
| Payment settles then reverses days later | Week is a state machine, never a boolean |
| Retry double-charges a customer | `Nonce` on every money-moving call |
| Call made without `Current-Merchant` | Executes against Upfront's own merchant. Wrap the client so the header is structurally impossible to omit |
| Hard dishonour retried | Burns a $5 decline fee for nothing. Classify before retrying |
| Business fails mid-book | Continuation factor by asset class, PPSR recovery, investor loss disclosed up front |
| Deal listed but not funded | Auto-spread default, plus a warehouse line concept |
