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

### 1. EXP-034 — Is the skill curve a step function? *(Q7, now the top question)*

EXP-030 closed Q1 and made this worse. On `press` every non-searching agent
lands between 4.5% and 10.5% while searching agents take 39-58%. That is not a
difficulty curve, it is a cliff at "can you plan two moves ahead", and a human
lives on the wrong side of it.

Build a graded family of intermediate agents — one-step lookahead, two-step with
a shallow evaluation, the miner with better target selection — and plot the
curve. If it is a step rather than a ramp, find what the searching agents know
that the others do not, and ask whether the game can *show* it (a preview, a
threat readout, a legibility change) rather than requiring the player to
simulate it. This is a comprehension problem wearing a difficulty costume.

### 2. EXP-033 — Has self-detonation become routine?

On `press` the player burns out ~3.5 times per run and ends with 7.25 of 10
capacity gone. D-005 earned burnout its place as a *dramatic choice*; at this
frequency it is a cost of doing business. Measure whether burnouts are chosen
(a planned blast that kills something) or suffered (unavoidable overflow), and
if mostly suffered, either raise the cost or give the player a real dump valve.

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
