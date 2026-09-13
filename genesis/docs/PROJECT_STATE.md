# PROJECT_STATE.md

*What exists and works, as of 2026-09-13.*

## The game — **OVERLOAD**, v0.5 prototype

A turn-based tactical duel on a closed ring of 12 nodes. One integer per unit,
`charge`, is simultaneously its ammunition, its power level and its death clock.
Charge is **conserved**: it is never created or destroyed inside an encounter.

**Two verbs.** `STEP` (move one node; fill up from any loose charge there) and
`SHOVE` (push up to `throughput` charge into an adjacent node, or your own).

**Three load-bearing rules.**
1. A unit dies when charge goes **over** capacity. Full is lethal, empty is helpless.
2. Picking charge up fills you to capacity and leaves the rest, so **only a
   directed transfer — a shove or a blast — can kill**. Nothing dies by accident.
3. Any unit at ≥50% capacity runs **hot** and acts twice. That includes you.

Overloading yourself does not end the run: you detonate where you stand, the
blast still happens, and you permanently lose capacity. Self-immolation is a
legal move and a good one.

**Playable now**: `genesis/index.html` — open it through any static server. The
client imports the same modules the experiments run against, so play and
measurement cannot drift apart.

## Status by evidence

| Claim | Evidence | Confidence |
|---|---|---|
| Skill decides outcomes | optimizer 41.7% vs random 0.3% vs turtle 0.0% on 300 shared seeds | HIGH |
| No degenerate economy is possible | conservation holds exactly across ~10^4 encounters | HIGH |
| The board does not play itself | kill causes are 55% player shove / 35% blast / 0% floor | HIGH |
| Depth is not reducible to a rule | hand-written expert policy reaches 8.3%, search reaches 41.7% | MEDIUM |
| Chains are real emergence | 71.7% of optimizer runs contain one; max length 6 | MEDIUM |
| Charge is a felt *death clock* | **not demonstrated** — see OPEN_QUESTIONS Q1 | LOW |

## Known defect (top of the queue)

**36% of encounters deadlock.** Two adjacent units pass the same charge back and
forth indefinitely; neither can ever overload the other. The rate is *identical*
at turn limit 45 and 120, so it is a genuine fixed point of the rules, not a
pacing problem. Diagnosed, not yet fixed — candidates in NEXT_EXPERIMENTS.md.

## The lab

```
genesis/
  index.html  web/            playable client (same modules as the sim)
  sim/        rules.js        the engine; no presentation code allowed here
              config.js       every mutable rule, as data. Experiments are overrides.
              content.js      archetypes + encounters, data only
              rng.js          seeded RNG whose state lives inside the game state
  agents/     index.js        random, conservative, greedy, explorer, bomber, miner, optimizer
  exp/        runner.js       harness; asserts conservation on *every* transition
              batch1..5.js    the recorded experiment batches
              ccr.js          the energy-budget phase sweep
  test/       core.test.js    8 invariant tests
  tools/      trace.js        human-readable replay of one seed
  docs/                       this laboratory's memory
```

`npm test` runs the invariants. `node exp/batch1.js` etc. reproduce every number
quoted in EXPERIMENTS.md; all runs are seeded and deterministic.

## Deviation from the brief

The brief assumes Godot 4. This environment has no Godot, and the bottleneck for
this project is **headless simulation throughput**, not rendering — a single
batch plays ~4,000 encounters. Zero-build ES modules run unmodified in Node for
experiments and in a browser for play, which also removes the usual
sim/presentation drift. If the project later needs real game feel, the engine is
a pure, dependency-free module that a Godot front end could drive as-is.
