# PROJECT_STATE.md

*What exists and works, as of 2026-09-13.*

## The game — **OVERLOAD**, v0.6 prototype

A turn-based tactical duel on a closed ring of 12 nodes. One integer per unit,
`charge`, is simultaneously its ammunition, its power level and its death clock.
Charge is **conserved**: it is never created or destroyed inside an encounter.

**Two verbs.** `STEP` (move one node; fill up from any loose charge there) and
`SHOVE` (push up to `throughput` charge into an adjacent node, or your own).

**Four load-bearing rules.**
1. A unit dies when charge goes **over** capacity. Full is lethal, empty is helpless.
2. Picking charge up fills you to capacity and leaves the rest, so **only a
   directed transfer — a shove or a blast — can kill**. Nothing dies by accident.
3. Any unit at ≥50% capacity runs **hot** and acts twice. That includes you.
4. A unit that holds nothing for long enough **dissolves** — it holds no charge,
   so removing it costs conservation nothing. Enemies that run dry go and refill
   from the floor rather than standing around, so an emptied enemy is a threat
   that has gone shopping, not a permanent wall.

Overloading yourself does not end the run: you detonate where you stand, the
blast still happens, and you permanently lose capacity. Self-immolation is a
legal move and a good one.

**Playable now**: `genesis/index.html` — open it through any static server. The
client imports the same modules the experiments run against, so play and
measurement cannot drift apart.

## Status by evidence

Panel on 400 shared seeds, encounter `surge`, v0.6 defaults:

| agent | win | loss | timeout |
|---|---|---|---|
| random | 2.0% | 22.5% | 75.5% |
| explorer | 5.8% | 20.3% | 74.0% |
| conservative (turtle) | 8.0% | 46.3% | 45.8% |
| miner (explicit expert policy) | 17.0% | 36.5% | 46.5% |
| greedy | 24.5% | 62.7% | 12.8% |
| **optimizer** (2-ply search) | **61.5%** | 14.0% | 24.5% |

| Claim | Evidence | Confidence |
|---|---|---|
| Skill decides outcomes | optimizer 61.5% vs random 2.0% on 400 shared seeds; six distinct rungs | HIGH |
| No degenerate economy is possible | conservation holds exactly across ~10^4 encounters | HIGH |
| The board does not play itself | kill causes are player shove / blast / starvation; 0% ambient floor | HIGH |
| Depth is not reducible to a rule | hand-written expert policy reaches 17.0%, search reaches 61.5% | MEDIUM |
| Chains are real emergence | 98.8% of optimizer runs contain one; max length 6 | MEDIUM |
| Findings replicate across shapes | validated on `surge` and `swarm`; two other encounters are low-CCR controls | LOW-MEDIUM |
| Charge is a felt *death clock* | **not demonstrated after four attempts** — see OPEN_QUESTIONS Q1 | LOW |

## Known defects

1. **24.5% of encounters still do not resolve.** Down from 40.8% once spent
   bodies were made to dissolve (D-012), but the residual is untraced. Two
   earlier attempts to fix the deadlock failed because the mechanism was
   *assumed* rather than observed — do not propose a third rule before tracing
   one of the remaining timeouts.
2. **The player's own capacity is not yet a source of tension** (Q1). Four
   experiments have failed to make the player approach their own overload.
   This needs a decision, not more tuning.
3. **Rules that widen the skill gradient keep doing it by punishing the middle**
   of the ladder rather than rewarding the top (Q7).

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
              batch1..7.js    the recorded experiment batches
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
