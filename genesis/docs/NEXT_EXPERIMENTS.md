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
> 7. **Ask what the do-nothing agent scores.** A turtle is the cheapest exploit
>    detector in the panel and has caught four separate mechanics that looked
>    fine on the win rates of agents that were trying (D-024).
> 8. **Confirm a surprising delta at 300+ seeds.** 150 seeds gives ±11pp on a
>    difference between arms; EXP-040 nearly recorded a sign-flipped finding
>    (D-026). Quote the seed count beside every number.

### 1. Human playtest — the first thing here a simulation cannot do

Two results now sit on the notebook's critical path and neither can be settled
by an agent:

- the depth-1/depth-2 legibility fix (EXP-034) is **unvalidated by
  construction** — every agent has perfect information, so no simulation can say
  whether the "What it takes" panel changes what a person attempts (D-020);
- the 50-65% target band adopted in EXP-039 is a **taste call**, honest only in
  that it was declared before sweeping.

One person, five runs of `surge` and five of `press`, thinking aloud, would
settle both and is worth more than any further agent batch.

### 2. EXP-041 — Re-derive `press` around `shovePushes`

EXP-040 retracted the rationale for killing displacement: against a working
instrument it *widens* the skill gap (27.1pp → 30.3pp) while lifting the whole
ladder, rather than flattening it as EXP-019 claimed. It was not adopted only
because it overshoots the target band on an encounter calibrated without it —
which is a tuning objection, not a design one.

Re-derive `press` with `shovePushes: true` using the EXP-039 machinery and the
same declared target. If it lands in band with a ladder at least as good as the
current one, the verb becomes positional as well as economic — which is a large
increase in what `SHOVE` does per rule, the standard this project has used for
mechanical density since the start.

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
