# 07 — Regulatory reality

Not legal advice. Nobody here is a lawyer. This is the shape of the problem so
you can answer "is this legal?" credibly, and so the prototype does not make
claims a real one could not.

## The core issue

Pooling retail money to fund businesses is a regulated activity in Australia.

- Marketplace and P2P platforms typically need **two** licences: an **AFSL** for
  the investment activity, because pooling funds from multiple investors is
  generally a **Managed Investment Scheme**, and potentially an **Australian
  Credit Licence** for the credit activity.
  [source: afslhouse.com.au, private credit and marketplace lending]
- ASIC's **INFO 213** focuses on obligations relevant to products structured as
  an MIS, which it found to be the common marketplace-lending model in Australia.
  [source: asic.gov.au marketplace lending]
- A scheme must be **registered** with ASIC if it has **20 or more investors**,
  or is promoted by a professional. Exemptions exist for wholesale clients and
  small-scale schemes raising under $2 million.
  [source: afslhouse.com.au, MIS and AFSL requirements]
- ASIC has granted **relief** to most retail marketplace-lending models it has
  licensed, including relief from registering a separate scheme per loan.
  [source: asic.gov.au marketplace lenders]

## Does "we buy receivables, we don't lend" help?

Partly, and it is worth saying. Factoring is the purchase of an asset at a
discount, not a loan; Australian guidance notes invoice finance is not a
traditional loan and does not appear as debt on the balance sheet.
[source: money.com.au invoice finance]

That materially changes the **credit-licence** analysis on the business side. It
does **not** dissolve the MIS question on the investor side — pooling retail
money to buy a portfolio of receivables is still collective investment.

And there is a wrinkle specific to this product. As `05-honest-returns.md`
argues, buying future **subscription** revenue is not really factoring, because
the service has not been delivered and the stream dies with the business. That is
closer to **revenue-based financing**, which looks more like lending. The invoice
book has the cleaner legal story as well as the cleaner economics.

## Two things to change in the product today

**1. Rename the grades.** ASIC has said alphanumeric ratings of the kind used by
traditional ratings agencies should not be used to describe borrower
creditworthiness, and that quantitative descriptions must carry enough
information to explain them. [source: Lexology on ASIC P2P guidance]

"Grade A-" reads exactly like an agency rating. Switch to something obviously
proprietary — **Rail Score 1-5**, or Verified / Strong / Watch / Caution. It is a
ten-minute change and it demonstrates real regulatory awareness.

**2. Add an investor knowledge check.** ASIC has suggested an optional knowledge
test to help investors understand the product before investing.
[source: Lexology on ASIC P2P guidance] Three questions before a first
investment: capital is at risk, there is no early withdrawal, recourse is not a
guarantee. Twenty-minute build, and judges notice it.

## Client money

Investor funds and collections must sit in a **segregated trust account**, never
the operating account. Name it in the architecture. Do not open one for a
prototype.

## Language to remove from the current site

| Currently says | Problem | Replace with |
|---|---|---|
| "A protected yield" | Implies capital protection that does not exist | "A yield, with the downside shown" |
| "Recourse-protected, business-default-only risk" | Recourse against an insolvent business over a dead subscription stream is thin | "Recourse-backed. If the business fails you can lose capital" |
| "14.2%" alone in green | Single-point yield with no distribution | Mean, 5th percentile, probability of loss |
| "Grade A-" | Reads as an agency rating | Rail Score |

The `claims` guard enforces the yield-plus-downside rule across the docs. The
prototype should hold itself to the same standard.
