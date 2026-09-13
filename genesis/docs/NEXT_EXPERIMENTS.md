# NEXT_EXPERIMENTS.md

Ranked by expected information gain per unit of implementation cost.

> **Standing gates, all three earned the hard way.**
> 1. **Trace before proposing.** Both of this project's worst diagnostic errors
>    (D-010's invented oscillation, and the whole of batch 2) came from
>    reasoning about a mechanism nobody had observed.
> 2. **Decompose before believing.** A metric that has not been separated into
>    design / correctness / instrument is not evidence about the design — 60%
>    of the flagship "deadlock" was bugs and agent myopia (D-015).
> 3. **Replicate across shapes, and across instruments.** One encounter hid a
>    99% do-nothing walkover (D-014); one evaluation function hid a 3.6x
>    behavioural difference (D-016).
> 4. **Ask whether it is a content question before writing a fifth rule.**
>    Four rule experiments failed at Q1; one archetype settled it (D-017).
> 5. **Vary one faculty at a time.** A spread of win rates across a mixed agent
>    panel does not localise a skill — it sent us to the wrong encounter
>    entirely (D-021).
> 6. **Audit the evaluation for every persistent quantity the game tracks.**
>    If the state has it and the score does not, the agent trades it away and
>    looks like it is telling you something about the design (D-022).

### 1. EXP-039 — Re-derive the difficulty of both encounters *(Q9)*

The strongest agent now wins 97.0% on `surge` and 96.7% on `press`. Both were
tuned against agents that treated a permanent capacity loss as free (D-022), so
every balance number in the notebook is an underestimate of competent play.

Sweep wave size, arrival cadence, the charge enemies arrive holding, and lobber
count, against the **corrected** instrument. Target declared in advance, as in
EXP-030b: the strongest agent between 50% and 65%, random and the turtle both
below 5%, and the `press` near-overload finding intact above 30%. Do not
re-tune by taste — the last dose sweep worked because the target was written
down first.

### 2. Human playtest — the first thing here that a simulation cannot do

EXP-034 located the depth-1/depth-2 step precisely and the client now surfaces
the arithmetic that should close it. Every agent has perfect information, so
this fix is **unvalidated by construction** (D-020). One person playing five
runs of `surge`, with think-aloud, would settle whether the "What it takes"
panel changes what they attempt — and would be worth more than any further
agent batch on this question.

### 3. EXP-031 — Re-tune `surge` against the improved agent

The strongest agent now wins 78% (it won 41% two batches ago) and the encounter
has not moved. Difficulty numbers measured against a weaker agent are stale.
Sweep wave size, arrival cadence and the charge enemies arrive holding, and find
the setting where the strong agent lands nearer 50-60% without pushing random or
the turtle back above ~5%.

### 4. EXP-032 — Rebuild the low-CCR encounters as real content

`probe` (CCR 0.36) and `garden` (CCR 0.17) are unwinnable under every
configuration; they predate the energy-budget finding. Rebuild at CCR 0.8-1.2
with distinct compositions (siphon-heavy, warden-heavy) so the replication gate
runs against four *real* shapes instead of two plus two controls. This is what
makes every future finding trustworthy.

### 5. EXP-035 — Does starvation deserve to be a real strategy?

Starvation is ~4-8% of kills: it exists but is incidental. Is there a version
where deliberately tanking an enemy dry is a *chosen* line? It is also the one
mechanism that would make soaking charge attractive, so it may be a second door
into Q1. Test: give the player a verb that pulls charge *out* of an adjacent
unit onto the floor, and check whether a starve-focused strategy becomes
competitive without dominating.

### 6. EXP-036 — The first rule-changing upgrade (Q6)

Only after 1-3 resolve. Three candidates, each altering a *conversion* rather
than a number: `SHOVE` splits between the target and the tile beyond it; your
detonation does not cost capacity; absorbing over capacity sets a one-turn fuse
instead of killing you. Measure build divergence — do different upgrades produce
different action distributions, or the same game with different decoration?
