---
name: demo-check
description: Verify the sixty-second demo still runs clean end to end. Use before submitting, before a rehearsal, or after any change to the prototype or the engine.
---

Verify the demo path for `scope`, `$ARGUMENTS`, or the whole run.

Run `python3 tools/check.py check` first. If figures, tests, or guards fail, the demo is showing numbers the engine no longer produces and nothing else matters until that is fixed.

Then walk the path the judges will see, in order, and confirm each beat renders and each number on screen matches `engine/FIGURES.json`. Landing, connect, analysis, offer, funded, collections, marketplace, portfolio.

Check the three things that have broken before. The investor return figure must be the amortising number, not principal times rate times term. The fee drag panel must be present on the analysis screen, because removing it is how the model quietly becomes dishonest again. Any yield shown must have its downside shown within the same view.

Confirm the run is deterministic. The mock generator is seeded; if two consecutive runs differ, the seed is not being respected and the demo will diverge on stage.

Time the sixty seconds against a clock, not an estimate.

Final: which beats pass, which numbers are stale, and the single thing most likely to break in front of an audience.
