---
name: grill-pricing
description: Stress-test a pricing, underwriting, or risk assumption against the engine and the market data. Use when a rate, advance, yield, loss assumption, or fee treatment needs to be challenged before it goes in front of a judge or an investor.
---

Stress-test `assumption`, `$ARGUMENTS`, or the pricing decision under discussion.

Read first: `engine/pricing_engine.py`, `engine/portfolio_risk.py`, `engine/fees.py`, `docs/04-pricing-math.md`, `docs/05-honest-returns.md`, and `docs/06-market-data.md`. If the engine or the market data answers a question, use them instead of asking.

Do not produce a checklist of concerns. Find the single assumption whose failure would most change the answer, and attack that one.

The assumptions that have already broken once, in order of how much damage they did: processing fee drag treated as an afterthought rather than an underwriting input, subscription revenue modelled as a receivable when it is performance-contingent, business default probability set from the economy-wide base rate rather than the adversely-selected population, and expected loss quoted as a mean with no distribution behind it. Check whether the current assumption is a new instance of one of these before looking for anything more exotic.

Quantify the attack. Change the input in the engine and report what the answer becomes. An objection with no number attached is an opinion.

Then give your recommended assumption and name the trade-off you are accepting. Then stop and wait.

If the assumption is already defensible and the sensitivity is small, say so and name the next thing worth attacking instead.

One hard question, quantified, with your answer. No template.
