# NEXT_EXPERIMENTS.md

Ranked by expected information gain per unit of implementation cost. The top two
are forks in the design, not tweaks — do them before anything else.

### 1. EXP-020 — Transfer spill (candidate answer to Q2, the deadlock)

A fixed fraction of every shove lands on the floor instead of in the target.
Conservation is preserved; **reversibility is not**. Two units passing charge
back and forth now leak into the ground, which should break the fixed point and
simultaneously feed the floor economy that the rest of the design runs on.
*Predict before running*: timeout rate falls below 15%; optimizer win rises;
tip kills rise because the floor fills faster. *Risk*: it taxes the player's own
mine-building, which may hurt the strongest strategy.

### 2. EXP-021 — Stagger (the other answer to Q2)

A unit that received a shove this round cannot shove back until its next turn.
Directly targets the oscillation without touching the economy. *Predict*: bigger
effect on the deadlock than EXP-020, but adds a rule with no other consequences
— which by the mechanical-density standard makes it the worse fix even if it
scores better. Run both; prefer the one that pays elsewhere.

### 3. EXP-022 — Decide Q1 rather than tuning it

One experiment, two arms. **Arm A**: something forces charge onto the player —
e.g. an enemy archetype whose entire behaviour is dumping charge into the player
from range and which cannot be disarmed by being spent. **Arm B**: formally
retire the claim that the *player's* capacity is a source of tension, and move
that tension entirely onto enemy capacity. Measure top-quartile occupancy and
the skill gradient. Whichever arm wins, rewrite DESIGN_THESIS.md accordingly and
stop revisiting it.

### 4. EXP-023 — Replicate v0.5 across encounter shapes (Q5)

Run the full agent panel on `probe`, `swarm`, `garden` under v0.5 rules, and on
ring sizes 8 and 16. Any headline finding that does not replicate is a finding
about `surge`, and should be relabelled as such in DISCOVERIES.md.

### 5. EXP-024 — A fairer instrument (Q4)

Re-run the panel with an optimizer whose evaluation is purely outcome-based
(enemies alive, player alive, turn count) with the fear-of-overload term
removed. If its behaviour is unchanged, the current results are not an artefact
of the evaluation function. This is cheap and it de-risks every claim above.

### 6. EXP-025 — The first rule-changing upgrade (Q6)

Only after 1-3 resolve. Three candidates, each altering a *conversion* rather
than a number: `SHOVE` splits between the target and the tile beyond it; your
detonation does not cost capacity; absorbing over capacity is allowed but sets a
one-turn fuse instead of killing you. Measure build divergence — do runs with
different upgrades produce different action distributions, or the same game with
different decoration?

### Standing chore

`tools/trace.js` on three random seeds after any rules change, before trusting
any aggregate. Both of this session's most important findings (D-003, D-007)
were visible in a trace and invisible in the summary statistics.
