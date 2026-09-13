# NEXT_EXPERIMENTS.md

Ranked by expected information gain per unit of implementation cost.

> **Standing gate, earned the hard way.** Before adopting any rule: (a) trace
> three seeds and *look* at the board — both of this project's worst diagnostic
> errors (D-010, and the whole of batch 2) came from reasoning about a mechanism
> nobody had observed; (b) run the panel across every encounter shape — that
> check caught a 99% do-nothing walkover that was invisible on the encounter the
> rule was developed against (D-014).

### 1. EXP-026 — Trace the residual 24.5% of non-resolving encounters

Not a rule proposal. Dissolution took timeouts from 40.8% to 24.5%; nobody has
looked at what the remaining quarter are doing. The last two times we skipped
this step we burned a batch on an invented mechanism. Cheapest item on the list
and it gates everything else about pacing.

### 2. EXP-027 — Decide Q1 rather than tuning it *(unchanged from the last queue, and now overdue)*

Four experiments (EXP-008, 015, 017, and dissolution's side effect) have failed
to make the player occupy the dangerous end of their own capacity. One
experiment, two arms. **Arm A**: an archetype whose whole behaviour is forcing
charge onto the player from range and which cannot be disarmed by being spent —
note that a *hungry* enemy now refills, so this is newly buildable in a way it
was not in EXP-018. **Arm B**: formally retire the claim, and move the tension
entirely onto enemy capacity. Whichever wins, rewrite the thesis and stop
revisiting it.

### 3. EXP-028 — Rebuild the low-CCR encounters as content

`probe` (CCR 0.36) and `garden` (CCR 0.17) are unwinnable under every
configuration — they predate the energy-budget finding. Rebuild them at CCR
0.8-1.2 with distinct compositions (siphon-heavy, warden-heavy) so the
replication gate runs against four *real* shapes instead of two plus two
controls. This is what makes every future finding trustworthy.

### 4. EXP-029 — A fairer instrument (Q4)

Re-run the panel with an optimizer whose evaluation is purely outcome-based,
with the fear-of-overload term removed. If behaviour is unchanged, every claim
above is robust to the instrument. Cheap, and it de-risks the whole notebook —
especially Q1, where the current agent's evaluation explicitly encodes the thing
under test.

### 5. EXP-030 — Does starvation deserve to be a real strategy? (from D-012)

Starvation currently accounts for ~4% of the optimizer's kills — it exists but
is incidental. Is there a version where deliberately tanking an enemy dry is a
*chosen* line rather than a by-product? That is the one mechanism that would
make soaking charge attractive, so it may be the back door into Q1. Test: give
the player a way to accelerate drain (a verb that pulls charge *out* of an
adjacent unit into the floor) and measure whether a starve-focused strategy
becomes competitive without dominating.

### 6. EXP-031 — Is the mastery gap an accessibility problem? (Q7)

Rules from the last two batches widen the gradient by punishing the middle of
the ladder. Measure explicitly: build a "competent but non-searching" agent
panel at several skill levels and check the curve is smooth rather than a cliff
between "searches" and "does not".

### 7. EXP-032 — The first rule-changing upgrade (Q6)

Only after 1-3 resolve. Three candidates, each altering a *conversion* rather
than a number: `SHOVE` splits between the target and the tile beyond it; your
detonation does not cost capacity; absorbing over capacity sets a one-turn fuse
instead of killing you. Measure build divergence — do different upgrades produce
different action distributions, or the same game with different decoration?
