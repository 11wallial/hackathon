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

### 1. EXP-030 — Force-feed encounter: settle Q1 with content, not rules

Q1 is now well posed. The unbiased agent lives near overload 9.1% of the time on
`surge` and 0.0% on `swarm`, and the difference is *how hard the composition
pushes charge onto the player*. So build an encounter designed to force-feed —
several mid-throughput chasers arriving continuously, no siphons to drain the
floor — and measure top-quartile occupancy under **both** instruments. If it
clears 25%, the death-clock half of the thesis is real and belongs in content
rather than in rules. If it does not, retire the claim and say so in the thesis.
Four rule-level attempts have failed; this is the first content-level one.

### 2. EXP-031 — Re-tune `surge` against the improved agent

The strongest agent now wins 78% (it won 41% two batches ago) and the encounter
has not moved. Difficulty numbers measured against a weaker agent are stale.
Sweep wave size, arrival cadence and the charge enemies arrive holding, and find
the setting where the strong agent lands nearer 50-60% without pushing random or
the turtle back above ~5%.

### 3. EXP-032 — Rebuild the low-CCR encounters as real content

`probe` (CCR 0.36) and `garden` (CCR 0.17) are unwinnable under every
configuration; they predate the energy-budget finding. Rebuild at CCR 0.8-1.2
with distinct compositions (siphon-heavy, warden-heavy) so the replication gate
runs against four *real* shapes instead of two plus two controls. This is what
makes every future finding trustworthy.

### 4. EXP-033 — Does starvation deserve to be a real strategy?

Starvation is ~4-8% of kills: it exists but is incidental. Is there a version
where deliberately tanking an enemy dry is a *chosen* line? It is also the one
mechanism that would make soaking charge attractive, so it may be a second door
into Q1. Test: give the player a verb that pulls charge *out* of an adjacent
unit onto the floor, and check whether a starve-focused strategy becomes
competitive without dominating.

### 5. EXP-034 — Is the mastery gap an accessibility problem? (Q7)

Rules from recent batches widen the gradient by punishing the middle of the
ladder. Build a graded family of non-searching agents and check the curve is
smooth rather than a cliff between "searches" and "does not". A human lives in
that middle band.

### 6. EXP-035 — The first rule-changing upgrade (Q6)

Only after 1-3 resolve. Three candidates, each altering a *conversion* rather
than a number: `SHOVE` splits between the target and the tile beyond it; your
detonation does not cost capacity; absorbing over capacity sets a one-turn fuse
instead of killing you. Measure build divergence — do different upgrades produce
different action distributions, or the same game with different decoration?
