# 06 — Market data

Every external number this project relies on, with its source. Lines carrying a
`[source: ...]` tag are exempt from the `figures` guard; everything else in the
docs must come from the engine.

---

## Can you get a real business's book?

Short answer: **no, and you don't need to.** An individual SME's payment ledger
is private commercial data. Nobody publishes it, and any "real" book you found
circulating would be a privacy problem rather than an asset.

The useful move is different, and it is what the mock generator does: **build
synthetic books whose every parameter is calibrated to a public source.** That is
strictly better for a hackathon than a scraped real book, because you can defend
each number, and because you can construct the specific edge cases you need to
demonstrate — a concentration breach, a hard-fail cluster, a fee-drag trap.

If a judge asks "is this real data", the answer is:

> The books are synthetic. Every parameter in them is calibrated to a published
> source: gym membership economics from Viva Leisure's FY25 accounts, dishonour
> rates from published direct-debit failure data, loss rates from Prospa and
> Plenti's reported credit performance, insolvency base rates from ASIC. We can
> show you the source for any number on screen.

That answer is stronger than "we got a real book from a mate's gym".

---

## Public sources you can actually calibrate against

### Australian listed lenders — credit loss reality

| Source | Datum |
|---|---|
| Prospa (ASX:PGL) | Net bad debt **9.9%** of average gross loans FY23, up from **5.7%** FY22. Loan impairment charge A$139.4m. [source: bankingday.com, "Prospa's SME bad debts double", Aug 2023] |
| Prospa | Portfolio yield **34.8%** annualised in H1 FY23 — interest plus all fee income on average portfolio balance. [source: smbloan.com.au Prospa review] |
| Prospa | Expected credit loss allowance rose to **11.1%** of receivables at 30 June 2020, from 6.1% a year earlier. [source: Startup Daily, Prospa FY20 results] |
| Plenti (ASX:PLT) | Net credit loss rate **1.10%** FY25, **1.06%** FY24, **0.68%** FY23, **0.54%** FY22 — prime consumer, not SME. [source: plenti.com.au FY25 and FY23 results updates] |
| Plenti | 90+ day arrears **0.43%** at FY25 end. Management fee of **10%** deducted from investor interest. [source: plenti.com.au FY25 update; Plenti P2P lending guide] |

**How to use these.** Plenti is the floor: prime consumer credit, tightly
underwritten, sub-1% losses. Prospa is the ceiling: unsecured SME term lending,
5–10% losses at a 35% yield. Upfront's asset sits between them — SME-linked, but
collateralised by customer cash flows and short duration. Any loss assumption
outside that band needs an argument.

### Invoice trading and revenue marketplaces

| Source | Datum |
|---|---|
| Kriya (ex-MarketInvoice/MarketFinance) | Expected net yield to investors of **4–6%**, loan collection rate 78.01%, ~£3.4bn funded as at Nov 2023. [source: Financial Innovation (Springer), "Estimation of default and pricing for invoice trading (P2B)", 2024] |
| MarketInvoice | Since-inception default rate of **1.09% of all invoices**. Investors could take fractions as small as 1%; gross annualised returns advertised above 10%. [source: UK Parliament written evidence SME0154; AltFi MarketInvoice Investor Guide] |
| Pipe | Contracts traded at **92–98 cents on the dollar**; trading fee up to **1% per side**; 12-month maximum term; marketplace has since wound down. [source: Sacra company profile; founderpath.com Pipe comparison] |
| P2P invoice trading generally | Advance rates **70–90%**, discount rates **0.8–1.5% per 30 days**. [source: InvoiceInterchange] |

**The Kriya number is the one that matters.** A platform doing essentially this,
at scale, told retail investors to expect 4–6% net. If your model says 14%, you
need a structural reason, and "we collect on the rail and hold recourse" has to
carry that entire weight.

### Australian invoice finance pricing

| Source | Datum |
|---|---|
| Australian invoice finance | Fees typically **1.5%–4.5%** of invoice face value, varying with volume, debtor creditworthiness and payment terms. [source: smartsmssolutions.com AU business finance guide, Apr 2026] |
| Australian debtor finance | Advance rates commonly **80–85%** of invoice value. [source: money.com.au invoice finance, Jun 2026] |
| Effective cost | Service fee **0.5–3%** plus interest in the low-to-mid teens; annualised against funds received, facilities land **mid-teens to high-twenties per cent**. [source: scalesuite.com.au invoice finance for SMEs, Jul 2026] |
| International benchmark | Advance rates **80–95%**, sometimes to 95%; discount rate **1–5% per 30 days**. [source: SMBCompass; Crestmont Capital, 2026] |
| OptiPay (AU) | Financier fee ranges from **under 1% up to 3%** of invoice value. [source: businessdailymedia.com] |

### Payment failure rates

| Source | Datum |
|---|---|
| Global averages | Direct debit fails **6.5%** of the time, cards **7.9%**, digital wallets **11.5%**. [source: paychoice.com.au, direct debit dishonours] |
| Recovery | Intelligent retry recovers about **70%** of failed payments; **11–15%** of uncollected funds become bad debt. [source: GoCardless] |
| Direct debit reliability | Success rates of **95–100%**, against 80–95% for cards. About **30%** of subscription churn is involuntary. [source: GoCardless, why payments fail] |
| Dishonour fees | Australian banks charge payers **$10–$35** per dishonour. [source: paychoice.com.au; GoCardless AU] |

Net bad debt implied: 6.5% × (1 − 0.70) ≈ **1.95%**. The engine's scanner
produces 2.34% for Voltride and 1.57% for Northline, which brackets it correctly.

### Pinch's own pricing — an underwriting input, not an afterthought

[source: getpinch.com.au/legal/pricinginformation and helpdesk.getpinch.com.au]

| Item | Cost |
|---|---|
| Direct debit, domestic | **1.00% + $0.30** per transaction, **capped at $5.00** |
| Card, Visa/Mastercard domestic | **1.95% + $0.30** |
| Card, AMEX domestic | **2.50% + $0.30** |
| Declined bank-account collection | **$5.00** |
| Settlement transfer | **$1.00** |
| Dispute / chargeback | **$25.00** |
| Refund | equal to the original transaction fee |

Settlement timing: Visa and Mastercard typically settle one business day after
processing; AMEX and direct debit take two. Fees can be surcharged to the payer.
There are no setup, monthly or minimum fees. Volume discounts exist above
$100,000/month. [source: getpinch.com.au/pricing]

**The $5 cap is the single most important number here.** It makes large-ticket
collection nearly free and small-ticket collection expensive. On an $18,000
invoice the fee is $5, or 0.03%. On a $34.78 subscription debit it is $0.65, or
1.87%. That is a 60× difference in cost per dollar collected, and it is the
mechanism behind the whole cadence finding in `05-honest-returns.md`.

### Australian insolvency base rates

| Source | Datum |
|---|---|
| ASIC | **3,556** companies entered external administration in Q1 FY2025-26, from over 3.6 million registered companies. Down 2.1% year on year. **2.8 million** actively trading businesses at 30 June 2025. [source: Murrays Legal citing ASIC insolvency statistics, Jan 2026] |
| ASIC / RBA | Q1 FY26 produced 77 fewer corporate insolvencies than the prior year, the first decline in three years. The RBA's March 2026 Financial Stability Review described insolvency rates as stabilised around longer-run averages. [source: Sydney Collect, Australian Debt Collection Report 2026] |
| Volume | About **14,000** businesses per year enter formal insolvency. [source: australiametrics.org, ASIC insolvency statistics] |
| Industry mix | Construction is about **27%** of failures, accommodation and food services about **15%**, other services about **9%**. [source: scalesuite.com.au, business insolvency by industry] |
| FY24 trend | More than 11,000 companies entered external administration in 2023-24, a 39% increase year on year. [source: scalesuite.com.au citing ASIC] |

Base rate is therefore around **0.5% a year** across actively trading businesses.
The engine deliberately uses 3.5–9.0% because the financed population is
adversely selected. Prospa's realised experience is the justification.

### Payment behaviour and receivables

| Source | Datum |
|---|---|
| Xero Small Business Insights | The average Australian small business invoice is paid **more than six days after** the due date; on net-30 terms that is about 36 days to cash. [source: getwren.au citing Xero SBI, early 2026] |
| Late payment | Only **37%** of Australian B2B invoices are paid on time; **52%** run overdue; **11%** are eventually written off as bad debt. [source: payly.com.au citing Dynamic Business] |
| Atradius | **82%** of surveyed Australian businesses had invoices paid on time in 2026, improved on 2025. [source: clockify.me late invoice statistics citing Atradius] |
| Global DSO | Around **45 days** on recent industry compilations; Allianz Trade put average DSO at **59 days** in 2023 with one in five companies waiting over 90 days. [source: pencilpay.com; allianz-trade.com] |
| Concentration | Australian benchmarking guidance flags review when any single customer exceeds roughly **20%** of receivables. [source: scalesuite.com.au debtor days benchmarks] |

The 11% eventual write-off figure for AU B2B invoices is the strongest argument
for pricing invoice books wider on *credit* even while they are cheaper on *fees*.

### Subscription business economics — calibrating the contract books

| Source | Datum |
|---|---|
| Viva Leisure (ASX:VVA) | FY25 revenue **$211.3m**, **620,902** members, **491** locations. Corporate clubs average about **1,330** members at roughly 80% utilisation. Network membership reached about 680,000 by mid-FY26. [source: vivaleisure.group FY25 results; ausleisure.com.au, May 2026] |
| Implied | About **$340** revenue per member per year across the group, though this blends club, franchise and technology revenue. Single-club Australian memberships commonly sit in the **$15–25 per week** range. |

Northline Gyms in the mock set is built to this shape: 310 members at $15.95 a
week. That produces the 4.40% fee drag finding, which is a real property of real
Australian gym economics, not an artefact of the generator.

### SME borrowing costs — the alternative the business is comparing against

| Source | Datum |
|---|---|
| OECD | Interest rates on outstanding Australian SME loans **6.6%** in 2024, up from 6.5% in 2023; new loans steady at **6.5%**. [source: OECD, Financing SMEs and Entrepreneurs 2026] |
| Prospa | Business Loan Plus from **11.95%** APR, terms to five years, secured against property. [source: theadviser.com.au, Oct 2025] |
| Prospa unsecured | Portfolio yield **34.8%**. [source: smbloan.com.au] |

A business that can pledge property borrows at 6.5–12%. A business that cannot
pays Prospa around 35%. **Upfront's 23.56% sits between them, which is the honest
competitive position** — cheaper than unsecured SME credit, dearer than secured
bank debt, available to businesses that cannot access the latter.

---

## Refresh policy

Pricing pages and quarterly results move. Before quoting any figure above in a
pitch, re-check the source. The `figures` guard will not catch a stale external
number, only an untraceable internal one — that gap is deliberate and it is your
responsibility, not the harness's.
