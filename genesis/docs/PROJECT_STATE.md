# PROJECT_STATE.md

*What exists and works, as of 2026-09-13.*

## The game — **OVERLOAD**, v1.0 prototype

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

Panel on 300 shared seeds, v1.0 defaults. **Agents now price their own
capacity** (EXP-038); every figure reported before v1.0 was measured with an
instrument that treated a permanent capacity loss as free, and therefore
understated competent play.

| agent | `surge` win | `press` win | near-overload on `press` |
|---|---|---|---|
| random | 2.7% | 8.3% | 7.3% |
| explorer | 2.3% | 14.0% | 6.1% |
| conservative (turtle) | 5.0% | 9.3% | 2.1% |
| greedy | 21.7% | 8.0% | 41.6% |
| miner (explicit expert policy) | 32.3% | 6.3% | 18.6% |
| optimizerNeutral (unbiased evaluation) | 88.0% | **96.7%** | **46.4%** |
| optimizer (2-ply) | 91.3% | 79.3% | 4.4% |
| optimizerDeep (3-ply) | **97.0%** | 75.3% | 4.2% |

| Claim | Evidence | Confidence |
|---|---|---|
| Skill decides outcomes | 97.0% vs 2.7% on shared seeds | HIGH |
| No degenerate economy is possible | conservation holds exactly across ~10^4 encounters | HIGH |
| The board does not play itself | kills are player shove / blast / starvation; 0% ambient floor | HIGH |
| Depth is not reducible to a rule | explicit expert policy 32.3%, search 97.0% | MEDIUM |
| The skill step is one action wide | depth 1 → 2 is +30.7pp on `surge`, 2 → 3 is +0.0pp | HIGH |
| Charge is a felt *death clock* | on `press` the agent that lives near overload wins **96.7%** against 75.3% for the deeper-searching agent that flinches | HIGH |
| Chains are real emergence | 99%+ of strong-play runs contain one; max length 6 | MEDIUM |
| Findings replicate across shapes | validated on `surge`, `swarm`, `press` | MEDIUM |

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

1. **Both encounters are far too easy for competent play** — 97.0% and 96.7%.
   This is now the top defect by a distance. Their difficulty was tuned against
   agents that were quietly setting fire to their own capacity (D-022), so every
   balance decision in the notebook needs re-deriving against the corrected
   instrument.
2. **The legibility fix for the depth-1/depth-2 step is unvalidated.** EXP-034
   located the gap precisely and the client surfaces the arithmetic that closes
   it — but agents have perfect information, so no simulation can say whether it
   helps a person (D-020). Needs a human.
3. **~5% of encounters are genuinely unresolvable.** Down from 40.8%; small
   enough that it is not the highest-value target.
4. **Deliberate self-detonation is gone and is not coming back cheaply.**
   `absorbCap` removed the affordance (EXP-036); restoring it was built, tested
   and killed (EXP-037/038). D-005's mechanism survives reactively.

## The lab

```
genesis/
  index.html  web/            playable client (same modules as the sim)
  sim/        rules.js        the engine; no presentation code allowed here
              config.js       every mutable rule, as data. Experiments are overrides.
              content.js      archetypes (drone, siphon, warden, lobber) and
                              encounters, data only
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
