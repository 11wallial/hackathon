# PROJECT_STATE.md

*What exists and works, as of 2026-09-13.*

## The game — **OVERLOAD**, v0.7 prototype

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

Panel on 400 shared seeds, encounter `surge`, v0.7 defaults:

| agent | win | loss | timeout |
|---|---|---|---|
| random | 2.3% | 4.5% | 93.3% |
| explorer | 3.3% | 5.5% | 91.3% |
| conservative (turtle) | 6.0% | 34.3% | 59.8% |
| greedy | 23.0% | 67.3% | 9.8% |
| miner (explicit expert policy) | 28.2% | 29.0% | 42.8% |
| optimizerNeutral (unbiased evaluation) | 55.5% | 8.5% | 36.0% |
| optimizer (2-ply search) | 78.0% | 11.8% | 10.3% |
| **optimizerDeep** (3-ply search) | **78.3%** | 15.5% | **6.3%** |

Eight distinct rungs. Two instruments with different evaluation functions are
kept permanently in the panel, because EXP-029 showed a single one is not a
neutral window onto the game (D-016).

| Claim | Evidence | Confidence |
|---|---|---|
| Skill decides outcomes | optimizer 61.5% vs random 2.0% on 400 shared seeds; six distinct rungs | HIGH |
| No degenerate economy is possible | conservation holds exactly across ~10^4 encounters | HIGH |
| The board does not play itself | kill causes are player shove / blast / starvation; 0% ambient floor | HIGH |
| Depth is not reducible to a rule | hand-written expert policy reaches 17.0%, search reaches 61.5% | MEDIUM |
| Chains are real emergence | 98.8% of optimizer runs contain one; max length 6 | MEDIUM |
| Findings replicate across shapes | validated on `surge` and `swarm`; two other encounters are low-CCR controls | LOW-MEDIUM |
| Charge is a felt *death clock* | **not demonstrated after four attempts** — see OPEN_QUESTIONS Q1 | LOW |

## The deadlock, fully decomposed

The headline defect of v0.5 was that 40.8% of encounters never resolved. It
turned out to be four different things, and only two of them were design:

| cause | share | kind | fixed by |
|---|---|---|---|
| traffic jam of spent bodies | ~16pp | **design** | dissolution (D-012) |
| two enemy-AI bugs | ~13pp | correctness | EXP-026 |
| search horizon | ~7pp | instrument | depth 3 (EXP-028) |
| genuinely unresolvable | **~5pp** | design | open |

Two batches were spent proposing *rules* for a number that was 60% bugs and
agent myopia. See D-015.

## Known defects

1. **~5% of encounters are genuinely unresolvable.** Down from 40.8%. This is
   now a small enough residual that it is not the highest-value target.
2. **The strongest agent wins 78%**, which may mean `surge` is now too easy for
   competent play. Watch item, not yet acted on — the agent got much better
   this batch and the encounter has not been re-tuned against it.
3. **The player's own capacity is still a weak source of tension** (Q1) —
   though EXP-029 showed our evidence for that was partly instrument bias, and
   the unbiased agent does play near overload 9.1% of the time on `surge`.
4. **Rules that widen the skill gradient keep doing it by punishing the middle**
   of the ladder rather than rewarding the top (Q7).

## The lab

```
genesis/
  index.html  web/            playable client (same modules as the sim)
  sim/        rules.js        the engine; no presentation code allowed here
              config.js       every mutable rule, as data. Experiments are overrides.
              content.js      archetypes + encounters, data only
              rng.js          seeded RNG whose state lives inside the game state
  agents/     index.js        random, conservative, greedy, explorer, miner,
                              optimizer (2-ply), optimizerDeep (3-ply),
                              optimizerNeutral (unbiased evaluation)
  exp/        runner.js       harness; asserts conservation on *every* transition
              batch1..7.js    the recorded experiment batches
              ccr.js          the energy-budget phase sweep
  test/       core.test.js    8 invariant tests
  tools/      trace.js        human-readable replay of one seed
              postmortem.js   aggregate final state of runs that failed to resolve
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
