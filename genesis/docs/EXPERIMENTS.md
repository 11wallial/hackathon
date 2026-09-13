# EXPERIMENTS.md

Rule: **hypotheses are written before the code runs and are never edited after
results arrive.** Corrections go in *Interpretation*, not in *Hypothesis*.

Decision vocabulary: KEEP / MODIFY / RETEST / COMBINE / ARCHIVE / KILL.

---

## Batch 1 — pre-registered 2026-09-13, before the engine existed

### EXP-001 — Is there a decision here at all?

- **Question**: Does the charge/overload core produce skill-sensitive play, or
  is it noise?
- **Hypothesis**: Win rate will be strongly ordered
  `random << greedy < optimizer`, with the optimizer at least 3x the random
  agent's win rate on the same seeds. If the ordering is flat, there is no game.
- **Change**: none — baseline measurement of v0.1.
- **Expected behaviour**: the optimizer should vary its shove amount by context
  rather than always shoving maximum.
- **Measurement**: win rate per agent over 400 shared seeds; distribution of
  chosen shove amounts; Shannon entropy of the shove-amount choice.
- **Result** (300 seeds, encounter `probe`):

  | agent | win | loss | timeout | Hshove | Hshove given band | bait kills/run |
  |---|---|---|---|---|---|---|
  | random | 1.7% | 2.7% | 95.7% | 1.77 | 1.76 | 0.10 |
  | conservative | 0.7% | 8.0% | 91.3% | 0.00 | 0.00 | 0.01 |
  | explorer | 2.0% | 3.0% | 95.0% | 1.92 | 1.92 | 0.15 |
  | greedy | 6.0% | 2.0% | 92.0% | 1.61 | 1.38 | 0.00 |
  | bomber | 0.0% | 19.0% | 81.0% | 1.20 | 1.11 | 0.13 |
  | **optimizer** | **44.7%** | 0.7% | 54.7% | 1.97 | 1.47 | **2.70** |

- **Interpretation**: the skill gradient is real and large (26x random, 7x
  greedy), so there *is* a game here. But three things the hypothesis did not
  anticipate dominate the picture:
  1. **Nobody dies.** Loss rate is ~1-8%; 55-96% of runs hit the turn limit.
     The encounter does not resolve — it runs down. Conservation means both
     sides spend into each other and the charge ends up inert on the floor.
     Spent chasers sit at 0 charge as permanent furniture (confirmed in the
     turn-5-onward trace of seed 1003). **This is the headline failure.**
  2. **The player never gets near overload.** Charge-band occupancy is
     `[0.23, 0.28, 0.49, 0.001]` — the top quartile is visited 0.1% of turns.
     The central tension of the thesis is not being *experienced*, because
     venting onto your own node is a free, always-available safety valve.
  3. **The winning strategy is not the one we designed.** 2.70 of the
     optimizer's 3.63 kills per run (74%) are strict bait kills, and its
     feed ratio is only 32% — it wins by putting charge on the *floor*, not
     into enemies. Greedy, which only ever shoves into enemies, wins 6%.
- **Decision**: **KEEP** the core, **MODIFY** urgently. Confidence HIGH on the
  skill gradient, HIGH on the non-resolution failure.

### EXP-002 — Is the "hot" rule the load-bearing counterpressure?

- **Question**: Does `charge ≥ 50% capacity ⇒ two actions` stop "always shove
  maximum" from dominating?
- **Hypothesis**: With the hot rule **off**, the greedy max-shove agent's win
  rate rises sharply (we predict +15 percentage points or more) and the
  optimizer's shove-amount entropy collapses toward 0 as it converges on the
  maximum. With it **on**, both remain moderate.
- **Change**: `config.hotRule = false`.
- **Expected behaviour**: without counterpressure, feeding an enemy is free, so
  maximum throughput is always correct.
- **Measurement**: greedy win-rate delta; optimizer shove-amount entropy delta.
- **Result**: greedy 6.0% → **39.0%** (+33pp, far beyond the predicted +15pp).
  Optimizer barely moved: 44.7% → 43.7%. Shove-amount entropy did **not**
  collapse: 1.97 → 1.98, distribution essentially unchanged.
- **Interpretation**: the first half of the hypothesis is confirmed emphatically
  and the second half is **falsified**. The hot rule is load-bearing, but not in
  the way we thought. It does not shape *how much* you shove; it decides
  *whether skill matters at all*. With it off, a trivially simple agent gets
  within 5pp of a searching agent — the skill gradient collapses from 7x to
  1.1x. That is a much stronger reason to keep it than the one we wrote down.
  The "how much to shove" decision is driven by something else entirely (see
  EXP-001 note 3: it is driven by exact mine thresholds).
- **Decision**: **KEEP** the hot rule. Confidence HIGH.

### EXP-003 — Lethal overload vs. burn-out overload

- **Question**: Should the player's own overload kill them outright, or blow up
  in place at a permanent capacity cost?
- **Hypothesis**: `burnout` (survive, lose capacity, payload still detonates
  outward) produces *more* interesting play than `lethal`: agents will
  occasionally overload themselves **on purpose** as an offensive move, which
  lethal mode makes impossible. We predict burnout raises the fraction of runs
  containing a player detonation above 5%, and that deliberate self-detonation
  appears in optimizer runs without us coding it as a tactic.
- **Change**: `config.overloadMode ∈ {lethal, burnout}`.
- **Expected behaviour**: "failure becomes a weapon".
- **Measurement**: player-detonation rate, win rate, run length, whether any
  self-detonation occurred while the optimizer had a safe alternative.
- **Result**: optimizer win 44.7% → **50.0%**; self-detonations 0.01 → **0.33
  per run**; chain rate 0.3% → 6.0%; mean turns 35.2 → 33.8. Greedy was
  unaffected (6.0% → 6.0%) — it never accumulates enough charge to overload.
- **Interpretation**: confirmed. Burnout does not merely soften a loss; it adds
  a *tactic* that lethal mode makes unreachable, and the searching agent adopts
  it unprompted while winning more often. Self-immolation as an offensive
  option is exactly the "failure state becomes useful" affordance we were
  looking for, and it is the only thing in v0.1 that reliably produces chains.
  Note the asymmetry: it rewards the agent that can *plan*, and is worthless to
  the one that cannot. That is the right shape for a mastery mechanic.
- **Decision**: **KEEP** burnout as the default overload mode. Lethal mode is
  retained as a config flag for difficulty experiments, not as the baseline.
  Confidence MEDIUM-HIGH (single encounter tested).

### EXP-004 — Does movement need to be economy?

- **Question**: Is auto-absorbing motes on `STEP` (movement = income = risk)
  doing real work, or is it incidental?
- **Hypothesis**: Turning auto-absorb off (motes become inert) will measurably
  flatten positional play: step-direction choices will correlate far less with
  mote locations, and the board-as-bank tactic disappears.
- **Change**: `config.absorbOnStep = false`.
- **Measurement**: correlation between chosen step direction and the
  larger-mote side; mean motes left on the board at encounter end.
- **Result**: with absorb **off**, optimizer win rate 44.7% → **0.0%** and every
  run times out. Step-toward-motes rate falls from 0.875 to 0.489 — i.e. from
  strongly directed to indistinguishable from a coin flip.
- **Interpretation**: confirmed, but the magnitude exposes something the
  hypothesis missed: absorb-on-step is not a flavour rule, it is the player's
  *only* income. With it off there is no way to refill, so nothing can ever be
  killed. That makes the result less informative than it looks — it did not
  test "is movement-as-economy interesting", it tested "can the player act at
  all". A cleaner retest needs an alternative income channel to compare against.
- **Decision**: **KEEP**; **RETEST** the underlying question with a fair
  control (queued as EXP-011). Confidence HIGH that it is load-bearing, LOW
  that we learned why.

### EXP-005 — Are chain detonations emergence or randomness?

- **Question**: Can a player *cause* chains, or do they just happen?
- **Hypothesis**: Chains of length ≥ 2 will occur in optimizer runs at least
  2x as often as in random-agent runs on the same seeds. If the rates are
  similar, chains are spectacle without agency and must be redesigned.
- **Measurement**: chain-length histogram per agent, same seed set.
- **Result**: chains are **essentially absent**. random 0.0%, greedy 1.0%,
  optimizer 0.3% of runs; maximum chain length observed was 2, out of ~1,100
  cascades. Only burnout mode lifted it (6.0%).
- **Interpretation**: falsified, and the cause is arithmetic rather than
  strategic. A detonation splits its payload evenly over three nodes, so a
  neighbour receives payload/3 — with capacities of 6-14 and typical payloads
  of 6-8, a neighbour receives ~2, which never overloads anything. Chains were
  designed as spectacle and delivered as a rounding error. The mechanic is not
  wrong; the *split* is wrong.
- **Decision**: **MODIFY** — test an outward-only blast split where the payload
  goes to the neighbours instead of being diluted across the centre (EXP-009).
  Confidence HIGH in the diagnosis.

### EXP-006 — Conservation invariant & degeneracy hunt (adversarial)

- **Question**: Can any action sequence create or destroy charge, or produce a
  repeatable resource-positive loop?
- **Hypothesis**: No. Conservation should hold exactly on every transition
  except explicit wave injection. We predict the adversarial agent finds zero
  energy-creating sequences and zero non-terminating cascades.
- **Measurement**: per-transition invariant assertion across ~10^5 transitions;
  adversarial search log.
- **Result**: **0 conservation violations** and **0 cascade-guard trips** across
  every run in batch 1 (~4,000 encounters, millions of transitions), plus 8
  targeted unit tests. Total energy equals cumulative wave injection exactly, at
  every transition, in every config variant.
- **Interpretation**: confirmed. Worth noting *what this buys*: the classic
  roguelike degeneracy (a resource-positive loop) is impossible by
  construction, not by balancing. We never have to hunt for infinite combos in
  the economy; we only have to hunt for dominant *strategies*.
  One caveat found while writing the tests: the first version of the burnout
  test failed, and the engine was right — the test had fabricated charge by
  hand. The invariant caught its own test author, which is mild evidence it is
  actually load-bearing.
- **Decision**: **KEEP**. Confidence HIGH.

---

## Batch 2 — pre-registered 2026-09-13, written before these configs were run

Baseline for this batch is **v0.2**: burnout is now the default overload mode
(EXP-003), and the optimiser breaks score ties toward spending fewer actions
(an agent fix, not a rules change — the old tie-break made it burn actions on
provable no-ops). v0.2 baseline on 150 seeds: optimizer 30.7% win / 69.3%
timeout; greedy 7.0%; miner 13.3%.

### EXP-007 — Circulation: do hungry enemies fix heat death?

- **Question**: D-001 says a conserved economy needs a rule that forces charge
  to keep moving. Does making spent chasers forage do it?
- **Hypothesis**: timeout rate for the optimizer falls by ≥30pp, mean turns
  falls, and loss rate rises above 5%. **Risk we are explicitly watching for**:
  if enemies suicide into any pile, the game plays itself — that would show up
  as *random* and *greedy* win rates jumping too, and would be a failure, not a
  success.
- **Change**: `hungryEnemies: true`.
- **Measurement**: win/loss/timeout and mean turns for random, greedy,
  optimizer, miner; bait kills per run; skill gradient (optimizer ÷ greedy).
- **Result**: the opposite of the prediction on every axis. Optimizer timeouts
  **rose** 69.6% → 86.0% and its win rate fell 30.4% → 14.0%. Random rose
  1.6% → 9.2% and greedy 6.0% → 12.8%. Skill gradient collapsed 5.1x → 1.1x.
- **Interpretation**: falsified, and **the risk we pre-registered is exactly
  what happened**. Foragers eat the charge the player is staging, so deliberate
  mine-building becomes unreliable (mean shove size fell to 1.55), while unskilled
  agents benefit from enemies blundering into scattered piles. The rule helped
  precisely the agents it was supposed to punish. The deeper error was the
  diagnosis itself: D-001 blamed circulation, and EXP-013 later showed the
  binding constraint was the total energy budget.
- **Decision**: **KILL**. Confidence HIGH.

### EXP-008 — Removing the free safety valve

- **Question**: D-002 says the danger half of the thesis is unimplemented
  because venting is a button. Does end-of-round settling implement it?
- **Hypothesis**: top-quartile charge occupancy rises from 0.1% to above 5%,
  near-overload rate rises, self-detonations rise, and every agent's win rate
  falls. We also predict a cost: staging charge for a mine gets harder, so bait
  kills fall.
- **Change**: `settleMotes: true`.
- **Measurement**: chargeBand, nearOverloadRate, selfDetonations, baitKills.
- **Result**: optimizer 30.4% → 6.4% win. Top-quartile charge occupancy:
  **0.001 before, 0.001 after**. Near-overload rate unchanged at 0.1%. The
  predicted cost did appear (bait kills 2.31 → 1.27).
- **Interpretation**: falsified. It paid the full predicted price and bought
  none of the predicted benefit. The reason is a plain design error on our part:
  settling closes the `dir = 0` vent while leaving the sideways vent (`shove` into
  an adjacent empty node) completely open, so disposal was never actually made
  expensive. We changed the valve we could see rather than the one that mattered.
- **Decision**: **KILL** as implemented. Confidence HIGH.

### EXP-009 — Making chains arithmetically reachable

- **Question**: D-006 says chains failed on a division, not on design. Does an
  outward-only blast split make them occur?
- **Hypothesis**: chain rate rises at least 3x over the v0.2 baseline and the
  maximum observed chain length exceeds 2.
- **Change**: `blastSplit: 'outward'`.
- **Measurement**: chain histogram, max chain, detonations per run.
- **Result**: chain rate for greedy 1.2% → **29.6%** and for miner 2.8% → 31.2%,
  vastly beyond the predicted 3x. But the optimizer barely moved (6.8% → 7.6%),
  max chain length stayed at 2, and loss rates jumped (greedy 0.4% → 12.0%).
- **Interpretation**: the arithmetic half of D-006 is confirmed — chains were
  unreachable, and changing the division made them reachable. But the benefit
  landed on the agents that stand next to things and die, not on the agent that
  plans, and the optimizer's win rate fell 30.4% → 23.6%. Under v0.2 rules this
  is a lethality change wearing a spectacle costume. Note that under v0.5 rules
  (`absorbCap`) chains reach 71.7% of runs and length 6 with the *even* split —
  the arithmetic fixed itself once payloads got bigger, which makes the outward
  split unnecessary.
- **Decision**: **ARCHIVE** (flag kept, default `even`). Confidence MEDIUM.

### EXP-010 — The v0.3 candidate (C1+C2+C3 together)

- **Question**: do the three fixes compose, or do they cancel?
- **Hypothesis**: timeouts below 25%, loss rate above 15%, and the skill
  gradient (optimizer ÷ greedy win rate) stays at 3x or better. If the gradient
  collapses we have made the game more decisive and less interesting, which we
  would count as a failure even if the pacing numbers look good.
- **Measurement**: full agent panel on shared seeds.
- **Result**: optimizer 18.8% win / 81.2% timeout; greedy 16.4%; gradient 1.1x.
  Worse than the v0.2 baseline on every measure that mattered.
- **Interpretation**: they compose, and they compose downward. Three
  independently-motivated fixes, all of which reduced the skill gradient,
  produced a game that is decisive-looking and less interesting. This is the
  batch's real lesson: after three consecutive local patches failed, the model
  of the problem was wrong, not the patches. Stepping back to compute the energy
  budget (EXP-013) found the actual constraint in five minutes.
- **Decision**: **KILL** the combination. Confidence HIGH.

### EXP-012 — Is the discovered strategy reducible to a rule? (mastery depth)

- **Question**: can an explicit hand-written policy for "salt the retreat"
  match a 2-ply search? If yes, the game's depth is shallow and mechanical.
- **Hypothesis**: written after the first miner version scored 8.3% and before
  the improved versions were run — an explicit policy will get *close to* the
  optimizer (within ~10pp) once it can build mines across multiple actions and
  retreat in order to mine, because the tactic looked simple in the trace.
- **Measurement**: miner vs optimizer win rate on shared seeds.
- **Result**: three successive versions of the explicit policy scored 8.3%,
  13.3% and 14.8% against the search agent's 30.4% on the same seeds — and under
  v0.5 rules, 8.3% against 41.7%. It never got within 16pp.
- **Interpretation**: **falsified, and this is good news.** The hand-written
  policy had to be extended twice as we learned what the search was actually
  doing: first to build a mine across several actions (a 2/6 drone needs 5 and
  throughput is 4, so one shove can never arm it), then to *retreat in order to*
  mine the tile behind it. Even with both, it captures under half the value. The
  winning line is not a rule, it is a two-step plan whose second half only
  becomes legal after the first half is played. That is the shape of a skill
  ceiling rather than a trick.
- **Decision**: **KEEP** the mechanic; keep `miner` as the "competent human"
  reference point in the panel. Confidence MEDIUM-HIGH.

### EXP-013 — The energy budget (charge-to-capacity ratio)

- **Question**: batch 2 tried three rule changes and every one of them made the
  game *worse*. Before changing another rule: is non-resolution a rules problem
  at all, or an arithmetic one? Encounter `probe` contains **17 charge** and
  destroying every enemy requires delivering **47**. Winning therefore demands
  recycling each detonation's payload into the next kill, at a ceiling of 8
  charge moved per turn, inside 40 turns.
- **Hypothesis**: CCR (total charge ÷ charge needed to clear) is the dominant
  variable, and it is not monotonic. We predict:
  1. timeout rate falls steeply as CCR rises past ~0.5;
  2. the **skill gradient peaks at an intermediate CCR (we predict 0.7–1.2)**
     and collapses at high CCR, because when charge is abundant a naive agent
     can simply shove things to death;
  3. at high CCR the player's loss rate rises sharply, since the same abundance
     fills the player.
  If (2) is wrong and the gradient rises monotonically with CCR, then scarcity
  is not what makes this game interesting and the thesis needs rewriting again.
- **Change**: new config dials `startCharge` (charge pre-scattered on the ring)
  and `capacityScale`, sweeping CCR from ~0.36 to ~2.0.
- **Measurement**: win/loss/timeout and gradient across the panel per CCR.
- **Result / Interpretation / Decision**: see **Batch 5 — EXP-013 — Result**
  below, recorded with the rest of the energy-budget work.

---

## Batch 3 — pre-registered 2026-09-13

Context: EXP-013 showed non-resolution was an arithmetic problem (17 charge
available, 47 required). Moving charge injection *inside enemy bodies* rather
than onto the floor (encounter `surge`) fixed resolution and killed the
73%-win turtle strategy. But a trace of seed 2011 shows the turtle returning
late: from turn 14 the optimal line is literally `end turn` repeatedly while
spawns wander into the 45-charge ambient pile left by earlier detonations.
**Loose charge is a sink that never drains, and it kills for free.**

### EXP-014 — Absorption fills to capacity instead of overloading

- **Question**: if picking charge off the floor can never overload a unit, does
  the board stop playing itself?
- **Hypothesis**: killing will require a directed transfer (a shove or a blast),
  so the fraction of kills caused by floor absorption drops to ~0 and the
  fraction caused by a player shove rises sharply. The turtle and random agents
  lose most of their remaining win rate. The bait tactic is not destroyed but
  *changed*: piles become a way to fatten an enemy into hot-and-brittle, and the
  player must still arrive to tip it over. We predict optimizer win rate falls
  (it loses free kills) but stays well above every other agent.
- **Risk being watched**: this also makes the floor safe for the *player*, which
  could remove player risk entirely. EXP-015 is the intended counterweight.
- **Change**: `absorbCap: true`.
- **Measurement**: kill-cause attribution (floor / player shove / enemy shove /
  blast), win rates across the panel, bait kills.
- **Result**: kill causes for the optimizer went from
  `{floor: 1752, blast: 177, shove-player: 80}` to
  `{shove-player: 898, blast: 636, shove-enemy: 323, floor: 0}`. Turtle 11% → 0%,
  random 1% → 0%. Optimizer 71.5% → 35.0% win with deaths 4% → 24.5%.
  Top-quartile charge occupancy 0.8% → 4.1%; max chain 4 → 6; chain rate
  52.5% → 71%.
- **Interpretation**: confirmed on every count, including the predicted cost.
  87% of kills used to require no decision from anybody; now none do. The
  predicted *change* to the bait tactic also happened — `baitKills` went to zero
  by construction and the replacement metric `tipKills` (fatten from the floor,
  then tip with a shove) records 3.3/run, so the mechanic did not die, it moved.
  The flagged risk did not materialise: the floor got safer for the player but
  deaths went *up* sixfold, because the danger is now other units' deliberate
  transfers rather than ambient accident.
- **Decision**: **KEEP**, default on. Confidence HIGH. This is the single most
  important rule found in the project so far.

### EXP-015 — Symmetric hot rule: make holding charge *powerful*

- **Question**: D-002 said the danger half of the thesis is unimplemented. Two
  batches of "make disposal expensive" failed. Invert it: the reason the player
  never carries charge may be that carrying it buys **nothing**. Enemies get a
  second action when hot; the player does not.
- **Hypothesis**: giving the player the same +1 action when at ≥50% capacity
  makes high charge a genuine power/risk trade. We predict top-quartile charge
  occupancy rises from 0.8% to above 10%, near-overload rate rises several-fold,
  and the optimizer's win rate rises while greedy's *falls* (greedy will park
  hot and be tipped over by an enemy shove).
- **Change**: `playerHotBonus: 1`.
- **Measurement**: chargeBand, nearOverloadRate, win rates, player death causes.
- **Result**: optimizer 71.5% → 82.5%; greedy 21.5% → 15.5% with deaths
  50.5% → 64.5%. But top-quartile charge occupancy moved **0.008 → 0.007** and
  near-overload rate stayed at 0.4%.
- **Interpretation**: half confirmed, half **falsified**, and the falsified half
  matters more. The bonus does exactly what we said it would do to the *agents*
  — it rewards planning and punishes recklessness — but it does nothing to the
  behaviour it was designed to produce. The player simply parks at 50-75%:
  hot enough for the bonus, nowhere near the cliff. Follow-up EXP-017 raised the
  threshold to 0.75 and 0.85 to close that gap; occupancy moved 0.7pp while the
  skill gradient collapsed from 2.1x to 0.9x, because a higher threshold mostly
  makes *enemies* safe. See D-008: this line of attack is exhausted.
- **Decision**: **KEEP** the bonus at threshold 0.5 for its effect on the skill
  gradient. **KILL** the hypothesis that voluntary accumulation can be made
  dangerous; it is now Q1, a fork to be decided rather than tuned.
  Confidence HIGH on the falsification.


---

## Batch 5 — the energy budget and the deadlock

### EXP-013 — Result

CCR sweep on `probe`, 200 seeds per cell, optimizer/greedy/random:

| startCharge | CCR | random | greedy | optimizer | timeouts (opt) |
|---|---|---|---|---|---|
| 0 | 0.36 | 2% | 7% | 28% | 72% |
| 10 | 0.57 | 48% | 30% | 76% | 24% |
| 20 | 0.79 | 64% | 21% | 91% | 8% |
| 30 | 1.00 | 67% | 21% | 95% | 4% |
| 45 | 1.32 | 60% | 13% | 100% | 0% |
| 90 | 2.28 | 21% | 6% | 100% | 0% |

**Interpretation**: prediction (1) confirmed — resolution is entirely a
budget problem. Prediction (2) **falsified in an instructive way**: the gradient
did not peak in the middle, it rose monotonically, but *only because greedy was
dying rather than failing to kill*, which makes the ratio meaningless. The real
signal is the one we did not predict: **random wins 48-67% in the mid band**.
Charge lying on the floor is a weapon nobody had to aim. That observation is
what produced EXP-014 and D-007, and it is the most valuable thing in this
batch. Prediction (3) confirmed: loss rates climb to 89-98% at CCR ≥ 2.
**Decision**: MODIFY — inject charge inside bodies, not onto the floor
(encounter `surge`); adopt CCR as a first-class design parameter. Confidence HIGH.

### EXP-018 — Enemy throughput as forced charge injection

- **Hypothesis** (pre-registered): if the player will not carry charge
  voluntarily (D-008), enemies shoving harder will force them up the band.
  Predicted near-overload rate to rise with `enemyThroughputScale`.
- **Result**: the opposite. 1x → 3x took near-overload from 3.6% to **0.9%** and
  the optimizer's death rate from 21% to 17%.
- **Interpretation**: falsified, and it exposed D-009 — in a conserved economy
  an enemy that hits hard empties itself in one blow, so damage is
  self-limiting. Kept at 1.5x, but for an unrelated reason: it widens the skill
  gradient from 2.1x to 3.4x.
- **Decision**: ARCHIVE as a danger lever, KEEP at 1.5x as a difficulty dial.
  Confidence HIGH.

### EXP-019 — Shove displaces the body

- **Hypothesis** (pre-registered): making `SHOVE` push the target one node
  further breaks the two-body deadlock and lets the player herd enemies onto
  piles. Predicted a substantial fall in timeouts.
- **Result**: timeouts rose (39% → 49%). Optimizer deaths halved (19% → 8.5%),
  greedy more than doubled (12.5% → 30.5%), gradient narrowed.
- **Interpretation**: falsified. It is a defensive tool, not an offensive one —
  see D-011. Proposed as reach, used as escape.
- **Decision**: ARCHIVE (flag retained, default off). Confidence MEDIUM-HIGH.

### EXP-011b — Is the deadlock a pacing problem? *(unplanned, 5 minutes)*

Timeout rate at turn limits 45 / 60 / 80 / 120: **37% / 36% / 36% / 36%**.
Flat. The 36% is a genuine fixed point of the rules, not a budget. This produced
D-010 and Q2, and it is the defect at the top of the queue.

---

## Session synthesis (brief §34)

1. **What we learned that is robust**: the core is skill-sensitive (41.7% vs
   0.3% on shared seeds); conservation eliminates economic degeneracy for free;
   and every death now traces to a decision.
2. **What was falsified**: that the hot rule shapes expert behaviour (it decides
   whether skill matters); that a conserved economy escalates (it runs down);
   that `SHOVE` is the attack (the floor is); that the player can be enticed
   toward their own overload (they cannot, three times over).
3. **Surviving on inertia**: the `bomber` agent (killed), the `probe`/`swarm`/
   `garden` encounters (untested under v0.5 — Q5), and arguably the player's
   own capacity as a design element (Q1).
4. **Biggest unexplored space**: rule-changing upgrades (Q6) — deliberately not
   entered, because the vertical-slice gate is not met while Q1 and Q2 are open.
5. **Are we locally optimising?** Partly. Batch 2 was three consecutive
   local patches that all failed; the win came from stepping back and computing
   the energy budget instead. That pattern is worth remembering: when three
   rule tweaks in a row fail, the model of the problem is wrong.

---

## Batch 6 — pre-registered 2026-09-13, before either rule was written

Target: the top defect (D-010 / Q2). 36% of encounters are a fixed point immune
to time — two adjacent units pass the same charge back and forth, each transfer
exactly undone by the reply. A conserved system needs at least one
**irreversible** move or some states cannot be reached from others.

### EXP-020 — Transfer spill

- **Question**: does making every transfer slightly lossy break the fixed point?
- **Hypothesis**: a fraction of each shove landing on the floor at the target's
  node makes an exchange non-undoable, so the oscillation drains instead of
  cycling. We predict the optimizer's timeout rate falls **below 20%** (from
  40.3%), its win rate rises, and `tipKills` rise because the floor fills faster
  from ordinary combat rather than only from detonations.
- **Risk being watched**: it taxes the player's own mine-building, which is the
  strongest strategy. If `tipKills` *fall* while timeouts improve, we have
  traded the best mechanic for pacing and should reject it.
- **Change**: `spillFraction` ∈ {0, 0.25, 0.5}.
- **Measurement**: timeout/win/loss across the panel, tipKills, skill gradient.
- **Result**: falsified. Optimizer timeouts **rose** 40.8% → 45.2% at spill 0.25
  (predicted below 20%) and win rate was flat. At spill 0.5 the game stopped
  entirely: **every agent 100% timeout, zero detonations**.
- **Interpretation**: two things went wrong, and the second is our fault.
  First, the diagnosis: spill reduces *delivery*, and the spill-0.5 collapse
  shows delivery is what resolves encounters — so the deadlock cannot be an
  oscillation, or making exchanges lossy would have drained it.
  Second, the implementation was not a fair test: `floor(amount × fraction)`
  means a shove of 1 spills nothing, and the agents immediately found that
  (mean shove size fell to 1.46 at spill 0.5). We built a tax that is free to
  dodge and then measured the dodge. A fair version would spill a flat amount
  per action. We are not rerunning it, because EXP-022 identified the actual
  cause and this rule addresses something that is not happening.
- **Decision**: **KILL**. Confidence HIGH on the diagnosis, LOW that the
  mechanic itself was fairly tested.

### EXP-021 — Stagger

- **Question**: does forbidding the immediate reply break the fixed point?
- **Hypothesis**: a unit that received a shove cannot shove on its next action,
  so the exchange cannot be symmetric. We predict a **larger** drop in timeouts
  than EXP-020. But by the mechanical-density standard this is the worse fix
  even if it scores better: spill pays into the floor economy that the rest of
  the design runs on, while stagger does one job and nothing else. We will
  prefer spill unless stagger wins clearly on the skill gradient too.
- **Change**: `staggerOnShove: true` (symmetric — applies to the player as well).
- **Measurement**: as above.
- **Result**: falsified in the same direction. Optimizer timeouts 40.8% →
  **57.6%** and win rate 40.8% → 20.4%; gradient collapsed from 3.0x to 1.7x.
- **Interpretation**: same root error as EXP-020 — it reduces the rate at which
  charge gets delivered, and delivery is what ends encounters. Two independently
  motivated fixes failing in the same direction is the signal that the model of
  the problem is wrong, which is the pattern already recorded after batch 2. We
  stopped proposing rules and went to look at a deadlocked board instead.
- **Decision**: **KILL**. Confidence HIGH.

### EXP-022 — Dissolution: a unit holding nothing is nothing

- **Context**: EXP-020 and EXP-021 both failed, and the trace of seed 1000
  (turns 37-45, nothing moves at all) shows why. The deadlock is **not** charge
  oscillation as D-010 claimed. It is a **traffic jam**: bodies block absolutely,
  late `surge` has 9 units on 12 nodes, chasers queue behind each other, and
  spent drones sitting at 0 charge are permanent walls that can never be cleared.
  Both previous "fixes" reduced delivery, which is why they made it worse.
- **Question**: if a unit at zero charge is removed, does the ring unjam — and
  does a second way to kill appear?
- **Hypothesis**: a unit holding no charge holds nothing, so removing it costs
  conservation nothing. We predict (1) optimizer timeout rate falls **below
  20%** from 40.8%; (2) a second kill path appears — starvation should account
  for **more than 15%** of kills, since chasers empty themselves into the player
  by design; (3) **and this is the interesting one** — because absorbing an
  enemy's attack is now progress toward killing it, the player has a reason to
  soak charge, so top-quartile charge occupancy rises above 8% from 2.6%. That
  would be the first mechanism to answer Q1, and it would arrive from a rule we
  added for an unrelated reason.
- **Risk being watched**: starving may dominate overfilling and kill the
  tip-kill mechanic, which is currently what the game is about. If `tipKills`
  collapse, this is a downgrade whatever it does to pacing.
- **Change**: `dissolveAfter` ∈ {0, 1} rounds at zero charge.
- **Measurement**: timeouts, kill-cause attribution incl. new `starved`,
  chargeBand, tipKills, skill gradient.
- **Result**: prediction (1) confirmed — optimizer timeouts 40.8% → **20.0%**
  at `dissolveAfter: 1` and win rate 40.8% → 66.8%. Prediction (2) confirmed —
  starvation appears as a kill path. The **watched risk did not materialise and
  inverted**: `tipKills` *rose*, 3.61 → 4.64, and chains went from 71.6% to
  98.0% of runs. Prediction (3) was **not** supported: top-quartile charge
  occupancy moved only 2.6% → 3.6%, nowhere near the predicted 8%.
  A grace-period sweep (0, 1, 2, 3, 5, 8, 12, 20 rounds) found a broad plateau
  rather than a knife edge: timeouts stay near 21% across the whole range, while
  longer grace steadily suppresses free wins (random 25.6% → 1.2%, turtle
  18.4% → 1.2%). `dissolveAfter: 8` was selected: optimizer 58%, miner 30%,
  greedy 24%, random 7%, turtle 5% — the first monotone five-rung skill ladder
  the project has produced.
- **Interpretation**: the fix works and it was cheap, but the honest summary is
  that the *diagnosis* was the hard part and we got it wrong twice before
  looking at a board. Note also that Q1 is still not answered: dissolution gave
  the player a reason to soak charge and they still did not do it. D-008 holds.
- **Decision**: **KEEP**, paired with EXP-025. Confidence HIGH.

### EXP-023 — Ring size (the control for EXP-022)

- **Question**: is dissolution doing anything that simply adding space does not?
- **Hypothesis**: enlarging the ring to 16 or 20 nodes relieves the jam too, so
  timeouts fall — but it is a pure dilution that adds no decision, and we
  predict it will *not* move the charge band or produce a second kill path.
  If ring size matches dissolution on every measure, prefer ring size as the
  simpler change; if it only fixes pacing, dissolution is the better rule.
- **Change**: `ringSize` ∈ {12, 16, 20}.
- **Result**: falsified, and this is the useful part. Ring 16 barely moved
  anything (optimizer timeouts 40.8% → 37.6%) and ring 20 was slightly *worse*
  (41.6%), with no change to the charge band and no second kill path.
- **Interpretation**: the jam is not geometric. Chasers pack against the player
  wherever the player is, so adding nodes adds empty ring behind the queue, not
  room inside it. This is exactly the control the experiment existed to provide:
  it rules out "just add space" and isolates dissolution as the real fix rather
  than a dressed-up dilution.
- **Decision**: **KILL** ring size as a fix; keep `ringSize` as a dial.
  Confidence HIGH.

### EXP-025 — Resurrecting `hungryEnemies` under v0.6 conditions

- **Context**: EXP-022's replication check (EXP-024) found dissolution is not
  universally safe: on drone-only `swarm` it takes the turtle agent to **99%**,
  because drones empty themselves into the player and then dissolve. The
  encounter solves itself. Dissolution alone is not adoptable.
- **Question**: `hungryEnemies` was KILLED in EXP-007. Every reason it failed
  has since been removed — back then the floor *killed* (enemies suicided into
  piles, which helped unskilled agents) and mines were the player's win
  condition. Under `absorbCap` a foraging enemy **fills to capacity and
  survives**, which loads it into hot-and-brittle, i.e. it does the player's
  setup work for them. Does the same rule now help?
- **Hypothesis**: pairing it with dissolution restores the threat that
  dissolution removes — an emptied chaser goes shopping instead of evaporating,
  and only dissolves when there is genuinely nothing left to pick up. We predict
  the turtle's win rate on `swarm` falls **below 25%** from 99%, that the skill
  gradient on `surge` does **not** collapse the way it did in EXP-007 (optimizer
  ÷ random stays above 5x), and that `tipKills` rise, because self-loading
  enemies are easier to tip.
- **Risk being watched**: the EXP-007 failure mode returning — foragers stealing
  the player's staged charge. If the optimizer's win rate drops sharply while
  random's rises, it is the same failure and dissolution must be reconsidered
  instead.
- **Change**: `hungryEnemies: true` together with `dissolveAfter: 8`.
- **Result**: on `swarm` the turtle fell **99% → 28%** and random **49% → 8%**.
  (The prediction said "below 25%" for the turtle; 28% is a near miss in the
  right direction, recorded as a miss.) On `surge`, `tipKills` rose 4.38 → 5.04
  as predicted, and the optimizer ÷ random gradient widened 8.5x → 29.2x.
  The EXP-007 failure mode did **not** return for the strongest agent
  (optimizer 60% → 59%) but it partly returned for the middle of the ladder:
  the miner fell 31% → 17% on `surge` and 90% → 53% on `swarm`, because
  foragers steal the charge it stages.
- **Interpretation**: confirmed, with a real cost recorded. A mechanic that was
  correctly killed can become correct later when its preconditions change —
  `hungryEnemies` failed in a world where the floor killed things, and works in
  a world where the floor loads them. The cost is that it punishes the
  merely-competent policy harder than the strong one, which widens the mastery
  gap; whether that is a feature or an accessibility problem is now Q7.
- **Decision**: **KEEP**. Adopted as v0.6 defaults with `dissolveAfter: 8`.
  Confidence MEDIUM-HIGH (two encounter shapes).

### EXP-024 — Replication across encounter shapes *(the check that saved EXP-022)*

- **Question**: does dissolution hold up outside `surge`?
- **Result**: **no**, and running this before adopting the rule is the only
  reason we found out. On drone-only `swarm`, dissolution alone took the turtle
  agent to **99%** — a completely degenerate encounter — because drones empty
  themselves into the player and then evaporate. `probe` (CCR 0.36) and
  `garden` (CCR 0.17) stayed unwinnable under every configuration, exactly as
  EXP-013 predicts: they are starved of energy, and no rule fixes arithmetic.
- **Interpretation**: a headline result measured on one encounter shape is a
  result about that shape. `probe` and `garden` are pre-CCR test beds from v0.1
  and should be relabelled as low-CCR controls rather than treated as content.
- **Decision**: **KEEP** replication as a standing gate before adopting any
  rule. Confidence HIGH.

---

## v0.6 — final panel (400 seeds, `surge`, adopted defaults)

| agent | win | loss | timeout | tip kills | chains |
|---|---|---|---|---|---|
| random | 2.0% | 22.5% | 75.5% | 1.17 | 20.0% |
| explorer | 5.8% | 20.3% | 74.0% | 1.93 | 29.0% |
| conservative (turtle) | 8.0% | 46.3% | 45.8% | 1.61 | 58.5% |
| miner | 17.0% | 36.5% | 46.5% | 2.58 | 70.3% |
| greedy | 24.5% | 62.7% | 12.8% | 2.88 | 78.5% |
| **optimizer** | **61.5%** | 14.0% | 24.5% | **5.09** | **98.8%** |

Versus v0.5: timeouts 40.8% → 24.5%, optimizer 40.8% → 61.5%, tip kills
3.61 → 5.09, chains 71.6% → 98.8% of runs. Shove-amount entropy is unchanged at
1.93 with conditional entropy 1.81, so the decision diversity survived the
change. Conservation violations: 0.

---

## Batch 8 — EXP-026, the residual timeouts

### EXP-026 — Trace the 24.5% that still do not resolve

- **Question**: what are the remaining non-resolving encounters actually doing?
  (Deliberately not a rule proposal — the last two times we skipped this step we
  burned a batch on an invented mechanism.)
- **Result** (`tools/postmortem.js`, 400 seeds, optimizer on `surge`):

  | measure | value |
  |---|---|
  | ring occupancy at the end | **26%** — the traffic jam is gone |
  | runs with enough charge left to finish | **100%** |
  | runs with exactly 1 enemy left | 53 of 105 |
  | runs where a siphon survives | 102 of 105 |
  | share of the last 45 actions that were a bare `end turn` | **61%** |
  | mean player charge | 32% of capacity |
  | mean loose charge on the floor | 36.7 |

  Trace of seed 3001, turns 40-45, is unambiguous:
  `. SIP14/14+13 .+15 .+2 .+4 YOU4/8 . . . . . SIP6/14` — a siphon sitting at
  **exactly 14/14**, one single point of charge from detonating, while the
  player idles four nodes away pressing end turn, and a second siphon flips
  between nodes 11 and 0 forever.

- **Interpretation**: three distinct defects, none of them the *design*.
  1. **Blocked-move oscillation (engine bug).** `if (!moveUnit(dir)) moveUnit(-dir)`
     means a unit whose path is blocked walks *backwards*. On a ring that is a
     stable 2-cycle: the second siphon wants node 2, node 1 is occupied, so it
     reverses, then re-approaches, forever.
  2. **Full scavenger no-op (engine bug).** `aiScavenge` returns after trying to
     absorb whenever it is standing on motes — but under `absorbCap` a full unit
     absorbs nothing, so it burns its action doing nothing, permanently.
  3. **Search myopia (instrument, not game).** Killing a siphon needs 15 charge
     delivered. The 2-ply optimizer can only see kills reachable inside this
     turn, so partial progress scores as pure loss (−1.5 per charge spent) and it
     never starts. Half the stuck runs are a winnable position the agent cannot
     see. This is Q4 arriving with evidence.
- **Decision**: fix (1) and (2) as correctness bugs; treat (3) as an instrument
  change and measure it **separately**, so we know how much of the 26% was the
  game and how much was us. Confidence HIGH.

### EXP-027 — Decomposing the residual: engine bugs vs. instrument

- **Hypothesis**: the two engine bugs are worth less than the myopia. We predict
  the bug fixes alone take optimizer timeouts from 26.3% to **below 20%**, and
  that adding a distance-to-goal term to the evaluation (total charge still
  needed to clear the board — the win condition's own metric, not a tactic)
  takes it **below 12%**.
- **Risk being watched**: the evaluation term is a Goodhart hazard. If it makes
  the agent chip mindlessly at big targets, `tipKills` will fall and the skill
  gradient will narrow. Either would mean we improved a number and damaged the
  game; the term would then be rejected even if timeouts improve.
- **Measurement**: staged — baseline, +bug fixes, +evaluation term — with
  tipKills and the full panel at each stage.
- **Result**: both halves falsified, in opposite directions.
  The two engine bug fixes alone took optimizer timeouts **24.5% → 10.3%** and
  win rate 61.5% → 78.0% (predicted only "below 20%") — they were worth far
  more than predicted. The distance-to-goal evaluation term then made things
  dramatically **worse**: timeouts 10.3% → **67.3%**, win 78.0% → 29.0%, tip
  kills 3.58 → 1.80, detonations 10.97 → 4.34.
- **Interpretation**: the pre-registered Goodhart watch fired exactly as
  written. Rewarding "reduce the charge still needed to clear the board" pays
  the agent for *loading* enemies without finishing them — partial progress
  scores nearly as well as a kill — so it hoards, parks at 25-50% capacity
  (band `[0.06, 0.84, 0.09, 0.01]`) and stops killing. A distance-to-goal
  heuristic is only safe when being closer is monotonically better, and in a
  game where a nearly-full enemy is *more dangerous* than an empty one, it is
  not.
- **Decision**: **KEEP** the bug fixes. **KILL** the distance-to-goal term.
  Confidence HIGH.

### EXP-028 — Is the rest of the residual myopia or design?

- **Hypothesis** (written before running): if the remaining timeouts are the
  search horizon rather than the rules, simply deepening the search from 2 to 3
  actions should cut them substantially without any rules change.
- **Result**: timeouts **12.0% → 5.0%**, win rate 75.5% → 82.5%, chains in
  100% of runs, at about 3x the compute (9.7s for 400 encounters).
- **Interpretation**: confirmed. This completes the decomposition of the
  original 40.8% deadlock, and the headline is that **most of a "design defect"
  was not design**:

  | cause | share of the original 40.8% | kind |
  |---|---|---|
  | traffic jam of spent bodies (D-012) | ~16pp | **design** |
  | two enemy-AI bugs (EXP-026) | ~13pp | correctness |
  | search horizon (this experiment) | ~7pp | instrument |
  | genuinely unresolvable | **~5pp** | design |

- **Decision**: **KEEP** `optimizerDeep` as the strong-play reference. The
  depth-2 `optimizer` stays the default so that every number recorded in earlier
  batches remains comparable. Confidence HIGH.

### EXP-029 — The neutral instrument (Q4), and a correction to D-008

- **Hypothesis** (pre-registered in the previous queue): if an optimizer with a
  purely outcome-based evaluation — no fear-of-overload term, no adjacency or
  hot penalties, no hint about how to kill anything — behaves like the standard
  one, the notebook's claims are robust to the instrument.
- **Result**: it does **not** behave the same, and the difference lands exactly
  where it matters most.

  | | standard optimizer | neutral optimizer |
  |---|---|---|
  | win (`surge`) | 78.0% | 55.5% |
  | top charge quartile | 3.0% | **12.5%** |
  | near-overload turns | 2.5% | **9.1%** |
  | tip kills / run | 3.64 | **4.82** |
  | win (`swarm`) | 79% | **99%** |

- **Interpretation**: two findings, one of them a correction to our own work.
  1. **D-008 was measured with a biased instrument.** Its claim is that nothing
     will make the player approach their own overload — but the agent producing
     that evidence had an explicit `-25 per point of headroom below 4` fear term.
     Remove it and near-overload play rises **3.6x**. D-008 is not overturned
     (9.1% is still not "living on the brink", and on drone-only `swarm` the
     neutral agent shows 0.0%), but its absolute form is too strong and is now
     corrected. Notably the corrected data *supports* D-008's own prescription:
     the danger band is occupied only on the encounter that forces charge onto
     the player, i.e. pressure, not incentive.
  2. **The signature mechanic is not an artefact.** Tip kills are *higher*
     under the unbiased evaluation (4.82 vs 3.64), so "load them from the floor,
     then tip them" is something the game rewards, not something our scoring
     function planted.
- **Decision**: **KEEP** `optimizerNeutral` permanently in the panel as an
  instrument check. Confidence HIGH on the bias, MEDIUM on its magnitude.


---

## Batch 9 — EXP-030, settling Q1 with content

### EXP-030 — The lobber: force charge onto the player from range

- **Context**: Q1 has failed four times at the *rules* level. EXP-029 then
  showed why the question was mis-posed: the unbiased agent already plays near
  overload 9.1% of turns on `surge` and 0.0% on drone-only `swarm`. The
  difference is how hard the composition pushes charge onto the player. So this
  is a **content** experiment, not a rule change.
- **The obstacle this has to clear**: on a ring, melee pressure is
  self-limiting three ways. Only two units can ever be adjacent to the player;
  D-009 says a hard hitter disarms itself; and the player moves 2-3 nodes a
  turn against an enemy's 1, so they can always kite. Any archetype that only
  threatens at range 1 cannot force-feed.
- **The design**: a **lobber** — throws charge at the player from range 2-4 and
  **cannot lob at range 1**. So closing the distance neutralises it, which makes
  it a positioning problem rather than a damage stat, and it composes with the
  existing rules: lobbed charge fills you, you must dump it, the floor fills,
  and hungry enemies refill from that floor and lob it back. That loop is the
  pump D-009 said melee could not provide.
- **Hypothesis**:
  1. top-quartile charge occupancy for the **neutral** optimizer exceeds **25%**
     on the new encounter (12.5% on `surge`);
  2. near-overload turns exceed **20%** (9.1% on `surge`);
  3. player deaths by self-overload rise materially.
- **Risks being watched, both of which would mean rejecting it**:
  (a) *unavoidable death* — if the strong agent's loss rate exceeds ~50% this is
  lethality, not tension; (b) *fake threat* — if the answer is trivially "stand
  next to the lobber", the agent will spend most of its turns adjacent to one
  and the decision is not a decision.
- **Measurement**: chargeBand, nearOverloadRate, deathCause, loss rate, and the
  share of player-turns spent adjacent to a lobber, under **both** instruments.
- **Result**: H1 and H2 confirmed with room to spare, and **risk (a) fired
  exactly as pre-registered on the first dose**: every agent died 95-100% of the
  time. Near-overload for the neutral agent was 31.5% (predicted >20%) and top
  quartile 39.5% (predicted >25%), so the mechanism worked and the dosage was
  absurd.

  A dose sweep against a target declared before running (strong agent losing
  25-45%, neutral agent still above 15% near-overload) gave a clean monotone
  response:

  | lobbers | strong win/loss/timeout | neutral top quartile | neutral near-overload | random |
  |---|---|---|---|---|
  | 1 | 97% / 1% / 3% | 16.8% | 12.1% | 11% |
  | 2 | 83% / 10% / 8% | 31.3% | 22.7% | 11% |
  | **3** | **51% / 34% / 16%** | **36.9%** | **29.6%** | 8% |
  | 4 | 20% / 64% / 16% | 42.4% | 37.0% | 3% |
  | 5 | 3% / 92% / 6% | 41.9% | 33.8% | 1% |

  **Risk (b) did not fire.** At the adopted dose the strong agent is adjacent to
  a lobber only 14.4% of turns and spends 69.6% of turns *inside* lob range, at
  mean distance 3.06. It cannot afford to close — the chasers pin it, and
  closing on one lobber exposes it to the others.

- **Interpretation**: **Q1 is answered, and the answer was content.** Four
  rule-level experiments (EXP-008, 015, 017, and dissolution's side effect)
  failed to make the player occupy their own danger band. One archetype moved it
  from 9.1% to 29.6%. D-008's prescription — *design the pressure, not the
  incentive* — turns out to have been pointing at encounter composition the
  whole time, and we spent four experiments looking for it in the rulebook.

  Why an archetype was needed at all is itself the finding: on a ring, melee
  pressure is capped three separate ways — only two units can be adjacent to the
  player, a hard hitter disarms itself (D-009), and the player moves 2-3 nodes
  per turn against an enemy's 1. No amount of melee tuning can force-feed. The
  lobber gets past all three by reaching over the front rank, and it stays a
  decision rather than a stat because it cannot throw at range 1.

- **Watch item**: the player now burns out ~3.5 times per run (mean capacity
  lost 7.25 of 10). Self-detonation was meant to be a dramatic choice (D-005);
  at this rate it risks becoming routine. Queued.
- **Decision**: **KEEP** the lobber and adopt `press` at 3 lobbers / charge 6.
  Confidence MEDIUM-HIGH (one encounter family, both instruments agree).

### EXP-030c — The adopted `press` panel, and the sharpest result in the project

400 seeds, `press` (3 lobbers, charge 6):

| agent | win | loss | timeout | top quartile | near-overload | tip kills |
|---|---|---|---|---|---|---|
| miner | 4.5% | 87.8% | 7.8% | 22.1% | 18.6% | 1.16 |
| random | 7.5% | 68.8% | 23.8% | 11.5% | 7.4% | 1.51 |
| greedy | 8.3% | 90.8% | 1.0% | 44.6% | 39.7% | 0.69 |
| conservative | 10.5% | 53.3% | 36.3% | 4.2% | 2.1% | 1.81 |
| optimizer (fear term) | 39.3% | 48.3% | 12.5% | 8.3% | 5.6% | 2.94 |
| optimizerDeep (fear term) | 52.5% | 33.8% | 13.8% | 8.5% | 5.9% | 2.65 |
| **optimizerNeutral (no fear term)** | **57.8%** | 36.0% | 6.3% | **38.8%** | **31.8%** | **3.33** |

**The unbiased agent wins, and it wins by living in the danger band.** It spends
31.8% of its turns near overload against the fear-term agent's 5.9%, and beats
even the deeper-searching fear-term agent. On an encounter that forces charge
onto the player, avoiding your own capacity limit is a **measurable mistake**.

That is the complete answer to Q1. Charge really is a death clock — but only
when the composition makes it one, which is exactly what D-008 prescribed and
what four rule-level experiments failed to find because they were looking in the
rulebook instead of the encounter list.

**Recorded honestly: `press` has a worse skill ladder than `surge`.** The
non-searching agents cluster between 4.5% and 10.5% with the turtle *above*
greedy and the miner last. It separates "searches" from "does not" and almost
nothing else, which makes Q7 (is the mastery gap an accessibility cliff?) more
pressing, not less. The two encounters now have distinct jobs: `surge` is the
well-shaped fight with eight rungs, `press` is the pressure test.

---

## Batch 10 — EXP-034, is the difficulty curve a step?

### EXP-034 — Isolate planning depth

- **Context**: Q7 is now the top open question. On `press` every non-searching
  agent lands between 4.5% and 10.5% while searching agents take 39-58%. But
  those agents differ in *many* ways (hand-written policy vs search, different
  evaluations), so the comparison cannot say whether depth is the variable.
- **Question**: holding the evaluation function fixed and varying **only**
  search depth, is the curve a ramp or a step?
- **Hypothesis**: a step, with the largest jump between depth 1 and depth 2
  (predicted **> 20pp**), and a much smaller increment from 2 to 3 (predicted
  **< 10pp**). The reason is mechanical: the game's signature line is *salt the
  retreat* — step away from a chaser, then mine the tile you just vacated — and
  the second half of that plan only becomes **legal** after the first half is
  played. A depth-1 agent cannot represent it at all, no matter how good its
  evaluation.
- **Why it matters**: if the cliff is exactly at "two-action plans", this is a
  **comprehension** problem wearing a difficulty costume. The response would be
  to make what a 2-ply search sees *visible* — show the player where each enemy
  will move next — rather than to tune any number.
- **Measurement**: `optimizerNeutral` at depths 1, 2, 3 on both `surge` and
  `press`, same evaluation throughout.
- **Result**: the shape was predicted correctly and the **framing that motivated
  the experiment was wrong**.

  | encounter | depth 1 | depth 2 | depth 3 |
  |---|---|---|---|
  | `surge` | 26.3% | **57.0% (+30.7pp)** | 57.0% (+0.0pp) |
  | `press` | 53.3% | 59.7% (+6.3pp) | 54.7% (−5.0pp) |

  Both numeric predictions hold on `surge` (>20pp then <10pp). But `press` —
  the encounter this experiment was written to investigate, because its panel
  looked like a cliff — is where depth matters **least**.

- **Interpretation**: two corrections.
  1. **`press` is not a planning cliff.** Its non-searching agents fail for
     unrelated reasons: greedy dies 90.8% of the time and the miner 87.8%. They
     are not losing to shallow planning, they are losing to charge management
     under pressure — and a depth-1 *searcher* handles it fine at 53.3%. The two
     encounters test genuinely different skills, which is a better outcome than
     the one we feared.
  2. **The mechanism on `surge` is not the one we named.** A follow-up scan
     (`tools/comboscan.js`) shows salt-the-retreat is real and strongly
     depth-gated — 4.2% of depth-2 turns against 0.4% of depth-1 turns, 2.5x the
     kills per run — but it accounts for only **6.2% of kills**. It cannot
     explain a 30pp gap.

     What does: depth 2 gets **7.07 kills per run against depth 1's 4.80**.
     A single shove delivers at most 4, and a drone at 2/6 needs 5. Depth 1 is
     mechanically *able* to shove twice in a turn, but it never starts, because
     the first shove alone leaves the enemy alive and scores as pure loss. The
     cliff is **committing to a kill that takes more than one action**.

- **Decision**: this is a **comprehension** problem, and the response is
  legibility rather than tuning (brief §26). A depth-2 search knows two things a
  new player does not: exactly how much charge a target still needs, and how
  much the player can actually deliver before the turn ends. Both are now shown
  on the board. Confidence HIGH on the measurement, MEDIUM on the fix, which is
  **untested against humans** — see the caveat below.
- **Honest caveat**: agents already have perfect information, so no agent
  experiment can validate a legibility change. What the agents established is
  *which* information separates depth-1 from depth-2 play. Whether surfacing it
  helps a human is unmeasured, and stays unmeasured until there is a human
  playtest.

---

## Batch 11 — EXP-036, is burnout still a choice?

### EXP-036 — Chosen or suffered?

- **Context**: D-005 is one of the better findings in this project — letting the
  player survive their own overload at a permanent capacity cost turned a
  failure state into a *tactic*, and the searching agent adopted self-immolation
  unprompted. On `press` the player now burns out ~3.5 times per run and ends
  with 7.25 of 10 capacity gone. At that frequency it stops being a dramatic
  choice and becomes a tax, which would quietly erode the original result.
- **Question**: what actually pushes the player over capacity?
- **The classification is already instrumented.** Every unit records the cause
  of the charge that last entered it. For a player detonation:
  - `floor` — the player *stepped onto* a pile knowing what was on it: **chosen**;
  - `lob` / `shove-enemy` / `blast` — an enemy put it there: **suffered**.
- **Hypothesis**: on `press`, more than **60%** of player detonations will be
  suffered rather than chosen, and fewer than **30%** will kill anything. On
  `surge` the split should be markedly less lopsided. If that holds, burnout on
  `press` is a tax and D-005's finding is encounter-specific rather than general
  — which is a correction to an existing result, not a new feature request.
- **If falsified** (mostly `floor`, or mostly killing something), burnout is
  still a choice and the high rate simply reflects a high-pressure encounter.
  No action, and Q8 closes.
- **Measurement**: player-detonation cause histogram and the number of enemies
  destroyed in the same cascade, on `surge` and `press`, under both instruments.
- **Result** (400 seeds each):

  | encounter | agent | self-det/run | chosen (floor) | suffered | blast killed something |
  |---|---|---|---|---|---|
  | surge | optimizerDeep | 2.88 | **0.0%** | 100% | **85.6%** |
  | surge | optimizerNeutral | 1.80 | **0.0%** | 100% | 76.6% |
  | press | optimizerDeep | 3.32 | **0.0%** | 100% | 50.0% |
  | press | optimizerNeutral | 3.51 | **0.0%** | 100% | 67.2% |

- **Interpretation**: both halves falsified, and **the classification itself was
  broken** — one of its two branches was unreachable and we did not notice when
  designing it. `floor` is 0.0% everywhere because of `absorbCap` (EXP-014):
  absorbing loose charge fills you to capacity and never past it, so the player
  *cannot* overload themselves by stepping onto a pile. The experiment was saved
  only by its second metric.

  That second metric says the real thing: on `surge`, **85.6% of player
  detonations kill at least one enemy** (1.02 kills per blast). The blast is
  doing work — but reactively.

  **The finding is a silent regression we caused ourselves.** D-005 earned
  burnout its place because the searching agent adopted self-immolation as a
  *deliberate offensive move*, and that evidence came from v0.1, where stepping
  onto a big pile could push you over. `absorbCap` was adopted three batches
  later for an unrelated reason (stop the board killing things without a
  decision, D-007) and, as a side effect nobody noticed, **removed the only way
  a player could choose to detonate**. What still carries the name is a
  consolation prize: when an enemy overfills you, your blast hurts it back. A
  genuine cap on what an enemy gains by overfilling you, but not a choice.
- **Decision**: Q8's premise was wrong — burnout has not become routine, it has
  stopped being a *decision*. **MODIFY**: test restoring deliberate
  self-detonation as a variant of an existing verb (EXP-037). D-005 is amended
  rather than retracted: its mechanism is sound, its affordance was lost.
  Confidence HIGH.

### EXP-037 — Restore the choice: `gorge`

*(Hypothesis and kill condition written before the run; the first attempt to
save them hit a shell quoting error, so they are transcribed here unchanged.)*

- **Question**: if `absorbCap` removed the player's ability to choose a
  detonation, is that ability worth having back?
- **Design constraint**: the complexity budget says no new verbs, so this is a
  *variant* of `STEP` — step onto a tile and take everything there, cap ignored
  — not a third verb. Enemies never get it: they are the reason the floor is
  dangerous, not the ones deciding to eat it.
- **Hypothesis**: a **niche mastery tool**. We predict searching agents use it
  on more than 2% of steps onto a charged tile, that it is worth less than 5pp
  of win rate, and that shallow agents gain nothing — the same asymmetric
  signature burnout had in EXP-003.
- **Kill condition, declared in advance**: if agents essentially never use it,
  or it costs win rate, it is dead weight and gets removed on the simplicity
  test rather than kept because we built it.
- **Measurement**: gorge usage, win-rate delta per agent, productive-blast
  share, and whether the chosen/suffered split finally moves off 0%.

- **Result, first pass** (400 seeds): agents use it heavily — 1.3-2.2 per run —
  and it is **catastrophic**: optimizerNeutral 55.5% → 22.0% on `surge`
  (−33.5pp), optimizerDeep 78.3% → 53.8% (−24.5pp), and on `press` −30.0pp and
  −10.0pp. Shallow agents never touch it (0.00/run), exactly as predicted.
  The chosen/suffered split did move: 32.8-60.1% of player detonations are now
  deliberate.
- **Interpretation, first pass — confounded, and we caught why before concluding
  anything.** Neither evaluation function contains a term for the player's own
  **capacity**. Permanent capacity loss is therefore literally free in the
  agents' eyes, while the kill it buys is worth +120. They are not demonstrating
  that gorge is bad; they are Goodharting an instrument that does not price the
  cost. This is D-016 for the third time, and it would have been easy to read
  the −33.5pp as a design verdict and kill a mechanic on it.
- **Decision so far**: do **not** judge gorge on this run. Fix the instrument
  first (EXP-038), then re-measure.

### EXP-038 — Price the player's capacity, then re-judge gorge

- **Question**: neither evaluation values the player's own capacity, so a
  permanent capacity loss costs the agent nothing. Does pricing it change the
  gorge verdict — and what else does it change?
- **Why this term is legitimate**: capacity is a persistent *outcome* quantity
  like being alive, not a tactical hint. It is the same kind of term as
  "enemies remaining". That is the distinction EXP-027 got wrong when it added
  a distance-to-goal heuristic, which was a hint about *how* to play.
- **Hypothesis**: with capacity priced, gorge usage falls by at least half and
  the win-rate penalty shrinks below 10pp; if gorge still costs win rate at
  every weight, it is genuinely bad and gets killed per its own kill condition.
- **Risk being watched, and it is a serious one**: pricing capacity may act as a
  *de facto* fear-of-overload term and undo EXP-029/Q1. If the neutral agent's
  near-overload rate on `press` falls below 15% (it is 31.8%), then the Q1
  finding is sensitive to this choice and that must be reported, not buried.
- **Measurement**: sweep capacity weight 0 / 4 / 8 / 15; gorge usage, win rate,
  near-overload rate on `press`, both instruments.
- **Result**: three separate outcomes, and the incidental one is the biggest.

  **(1) The pre-registered risk did not fire.** Near-overload for the neutral
  agent on `press` went **up**, 48.2% → 52.7%. Pricing capacity is not a
  disguised fear term — it values a permanent outcome, where the EXP-029 term
  feared a transient state. Q1's finding survives and strengthens.

  **(2) Gorge fails its own kill condition.** With capacity priced it costs
  −15.3pp (surge/deep), −2.7pp (surge/neutral), −1.7pp (press/deep) and −9.7pp
  (press/neutral). Never positive. Agents still *choose* it 1.1-2.2 times per
  run and lose win rate doing so — their evaluation says +90 (a kill at 120
  against 2 capacity at 25 apiece is not the whole cost), the outcome says
  otherwise. It is attractive and wrong, with no signal that it is a mistake.
  **KILLED** per the condition declared before the run.

  **(3) The incidental result dwarfs both.** Simply pricing capacity, with
  gorge off, moved win rates enormously:

  | encounter | agent | capW 0 | capW 25 |
  |---|---|---|---|
  | surge | optimizerDeep | 80.3% | **96.8%** |
  | surge | optimizerNeutral | 61.7% | 88.0% |
  | press | optimizerDeep | 51.7% | 74.8% |
  | press | optimizerNeutral | 54.3% | **97.2%** |

  A sweep to 80 found the plateau at 25, so that is the new default.

- **Interpretation**: **every difficulty number this project has reported was
  measured with an instrument that treated a permanent loss as free.** Agents
  burned capacity for short-term gain all the way back to v0.5, and every
  "the strongest agent wins X%" figure was an underestimate of competent play.
  This is D-016 a third time, and the most expensive instance: it did not
  mislead one experiment, it miscalibrated the difficulty of the whole game.
- **Decision**: **KEEP** capacity pricing at weight 25 as the default for both
  instruments. **KILL** gorge. Re-tune both encounters against the corrected
  instrument — now the top queue item. Confidence HIGH.

### v1.0 corrected panel (300 seeds, agents pricing capacity, gorge removed)

| agent | `surge` win | `press` win | near-overload on `press` |
|---|---|---|---|
| random | 2.7% | 8.3% | 7.3% |
| explorer | 2.3% | 14.0% | 6.1% |
| conservative (turtle) | 5.0% | 9.3% | 2.1% |
| greedy | 21.7% | 8.0% | 41.6% |
| miner | 32.3% | 6.3% | 18.6% |
| optimizerNeutral | 88.0% | **96.7%** | **46.4%** |
| optimizer | 91.3% | 79.3% | 4.4% |
| optimizerDeep | **97.0%** | 75.3% | 4.2% |

Two design findings survive the correction and get stronger:

- **Q1 is reconfirmed more decisively.** On `press` the agent that lives near
  overload wins **96.7%** against 75.3% for the deeper-searching agent that
  flinches from it — a 21pp gap, up from 5pp. Flinching from your own capacity
  limit is not a small mistake.
- **Q8 partly dissolves.** Self-detonations per run on `surge` fall from 2.88 to
  2.17 for the deep agent and from 1.80 to 1.41 for the neutral one, once
  capacity is priced. A competent player does not burn out three and a half
  times a run; a badly-instrumented one did.

And one new defect, larger than either: **both encounters are far too easy for
competent play** (97.0% and 96.7%). Their difficulty was tuned against agents
that were quietly setting fire to their own capacity.

---

## Batch 12 — EXP-039, re-deriving difficulty against a working instrument

### EXP-039 — Both encounters are tuned to a strength no player has

- **Context**: D-022. Every balance decision in this notebook was derived
  against agents that treated a permanent capacity loss as free. With capacity
  priced, the strongest agent takes `surge` 97.0% of the time and `press` 96.7%.
- **Target, declared before any sweeping** (the EXP-030b discipline — that dose
  sweep worked because the target was written down first):
  1. strongest agent between **50% and 65%**;
  2. **random and the turtle both below 5%** — the D-007 canary, so the board is
     still not playing itself;
  3. on `press`, the near-overload finding intact: neutral agent above **30%**;
  4. and a constraint the earlier sweeps did not have — the **skill ladder must
     stay monotone**, since EXP-030 produced an encounter that hit its numbers
     while scrambling the middle of the panel.
- **What is swept**: wave cadence, units per wave, and the charge enemies arrive
  holding — content, not rules. A difficulty problem should be fixed where the
  difficulty lives.
- **Hypothesis**: cadence will dominate. Arrival charge is double-edged in this
  game (fuller enemies are more dangerous *and* more brittle, D-012), so we
  predict raising it does less than it looks like it should, and that the
  workable setting is mostly "more bodies, arriving sooner".
- **Result**: the hypothesis is falsified twice, once in each direction.

  **Body count dominates, not cadence.** Holding cadence at 4 and adding two
  units per wave took the strongest agent from 98% to 77%; holding units and
  halving the cadence (4 → 2) only reached 89%.

  **Arrival charge is not merely weak — it is actively harmful.** Raising it 30%
  took the turtle agent from 3% to **53%** and random from 0% to 10%. Fuller
  enemies are hot, act twice, and detonate each other without the player
  involved. This is the same failure as the killed floor-scattered wave charge:
  *charge the player did not place arms the board against itself, and that
  rewards passivity.* We predicted this dial would underdeliver; it backfires.

  **A flaw in our own scoring function, caught mid-experiment.** The first
  ladder check only compared the middle of the panel to *random*, which passes
  trivially once random sits at 0% — it would have signed off on a setting where
  the turtle outranked the expert policy. It also used `miner` and `greedy` as
  the middle rungs, which D-021 already said is wrong: they are hand-written
  policies, not medium-skill players. Replaced with a **depth-1 searcher using
  the same evaluation as the strong agent** — someone who plays well but does
  not plan two moves ahead — and required to sit clearly above the floor and
  below the ceiling.

  **Adopted**: `surge` at cadence 3 with three extra bodies per wave; `press` at
  five lobbers. And note what that second one means: **EXP-030b rejected five
  lobbers as unsurvivable** (strongest agent 3%). The same content is now the
  right answer at 63%. Nothing about the encounter changed — the instrument did.
  That is D-022 made concrete.

### v1.1 panel (300 seeds, re-derived encounters, agents pricing capacity)

| agent | `surge` | `press` | near-overload (`press`) |
|---|---|---|---|
| random | 0.3% | 0.7% | 9.3% |
| explorer | 0.3% | 1.0% | 8.7% |
| miner | 1.0% | 1.7% | 18.1% |
| conservative (turtle) | 2.3% | 2.7% | 2.3% |
| greedy | 8.0% | 12.0% | 41.0% |
| neutralD1 (plays well, plans one move) | 18.7% | 32.3% | 49.1% |
| optimizerDeep (3-ply, fears overload) | 31.0% | 23.7% | 5.6% |
| **optimizerNeutral** (2-ply, unbiased) | **62.7%** | **60.3%** | **54.2%** |

- **Interpretation**: both encounters now sit in the target band with a genuine
  ramp rather than a step — on `surge`, 0.3 / 2.3 / 8.0 / 18.7 / 31.0 / 62.7.
  Q1 is reconfirmed a third time and more starkly than ever: the unbiased agent
  beats the *deeper-searching* one by 32pp on `surge` and 37pp on `press`, while
  spending 40-54% of turns near overload against 5.6-10.6%. Under real pressure,
  fearing your own capacity is close to fatal.

  **One honest casualty**: `miner` has collapsed to 1.0-1.7%. It encodes a
  v0.1-era strategy and has not kept up with six versions of rules changes. It
  is no longer a useful "competent human" proxy and should be read as a historical
  baseline; `neutralD1` is the middle rung now.
- **Decision**: **KEEP** both re-derived encounters. Confidence HIGH on the
  calibration, MEDIUM on whether the target band itself is the right taste call
  — that is a judgement no simulation settles.
