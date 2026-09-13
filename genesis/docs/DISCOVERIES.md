# DISCOVERIES.md

General principles this project has *earned through testing*. Each entry names
the evidence. Anything without evidence belongs in OPEN_QUESTIONS.md instead.

---

### D-001 — A conserved economy resolves the degeneracy problem and creates a new one

**Evidence**: EXP-006 (0 violations in ~4,000 encounters); EXP-001 (55-96% of
runs hit the turn limit).

If charge can neither be created nor destroyed, resource-positive infinite loops
are impossible *by construction*. That is a large, permanent saving: we never
have to balance an economy against runaway combos.

The price is the opposite failure. A closed system does not escalate, it
**runs down**. Both sides spend into each other, the charge ends up on the floor
or inside inert bodies, and the encounter reaches a low-energy equilibrium where
nobody can threaten anybody. Conservation guarantees no explosion *and* no
climax.

> **Principle**: a conserved economy needs a *circulation* rule, not a
> generation rule. The design question is never "where does energy come from",
> it is "what forces energy to keep moving".

### D-002 — A free safety valve deletes the tension it was built to regulate

**Evidence**: EXP-001 charge-band occupancy `[0.23, 0.28, 0.49, 0.001]`.

The whole thesis rests on "holding charge is powerful and dangerous". In play
the player spends 0.1% of turns in the dangerous band. The cause is that
venting (shoving onto your own node) is unconditional, instant, and costs one of
two identical actions. A risk the player can switch off at will is not a risk.

> **Principle**: a resource is only dangerous if *disposing of it* is a
> positional or temporal problem, not a button.

### D-003 — The best strategy was the one nobody designed

**Evidence**: EXP-001 — 74% of the optimizer's kills are strict bait kills;
feed ratio 32%; greedy (which only ever attacks directly) wins 6% against the
optimizer's 45%. Trace of seed 1003, turn 6: the agent places **exactly 5**
charge on the one node a 2/6 drone must path through, and the drone's own move
kills it.

We designed `SHOVE` as an attack and the floor as a side effect. Measurement
says the reverse: direct attack is the weak option, and the strong one is
**placing an exactly-lethal pile in a predictable mover's path**. The enemy's
own greed and pathing is the trigger; the player is laying mines made of their
own power.

This is worth more than the mechanic we intended, because it makes one act
simultaneously an attack, a discard, a positional commitment and a bet on enemy
behaviour — and because the arithmetic is visible, so a human can find it.

> **Principle**: when the searching agent wins with a verb you thought was
> incidental, the verb is the game. Amplify it before you polish anything else.

### D-004 — Counterpressure rules should be judged by the skill gradient, not by behaviour shift

**Evidence**: EXP-002 — removing the hot rule moved the optimizer's win rate by
1pp and its shove-amount entropy by 0.01, but moved a naive agent by **+33pp**,
collapsing the skill gradient from 7x to 1.1x.

We predicted the hot rule would change *how much* an expert shoves. It does not.
What it changes is whether being unsophisticated is punished. A rule can be
essential while being invisible in an expert's action distribution.

> **Principle**: measure counterpressure as the *gap between agents*, not as a
> change in the best agent's behaviour.

### D-005 — Giving a failure state an outward payload converts it into a tactic

**Evidence**: EXP-003 — burnout mode raised optimizer win rate 44.7% → 50.0% and
produced 0.33 deliberate self-detonations per run, unprompted, from a generic
evaluation function. Greedy gained nothing (0.0pp) because it cannot plan.

Letting the player survive their own overload at a permanent capacity cost, and
keeping the blast, turns "you screwed up" into "you spent something". It also
self-selects for skill: only an agent that can plan the blast benefits.

> **Principle**: a failure state that still produces its physical consequence
> can be spent deliberately. A failure state that just ends the run cannot.

### D-006 — Spectacle mechanics fail on arithmetic long before they fail on design

**Evidence**: EXP-005 — chains occurred in 0.3-1.0% of runs, max length 2, out
of ~1,100 cascades.

Chain detonations were not rejected by players or by strategy. They were
rejected by a division: splitting a payload over three nodes hands a neighbour
payload/3 ≈ 2, against capacities of 6-14. The idea was never tested, because
the numbers never let it occur.

> **Principle**: before concluding a mechanic is uninteresting, check whether
> the rules make it *reachable*. Frequency-zero is a measurement failure, not a
> design verdict.

---

### D-007 — If the environment can kill without a decision, the optimal strategy is to stop playing

**Evidence**: the turtle agent reached **73% win / 0% deaths** once charge was
scattered on the floor; a trace of seed 2011 shows the search agent pressing
`end turn` from turn 14 onward while spawns walked into an ambient 45-charge
pile. Capping absorption at capacity took floor kills from **1,752 to 0** and
turtle and random win rates to 0.0%.

Free kills are not a balance issue; they are an *agency* issue. The moment the
board can resolve a threat without the player choosing something, doing nothing
becomes a strategy, and it is usually the safest one.

> **Principle**: every death in the game should be traceable to a decision.
> Audit this directly — attribute each kill to its cause and look at the
> histogram. "Environment" should be near zero.

### D-008 — Nobody walks toward a cliff for one extra step

**Evidence**: EXP-015 gave the player a second action at ≥50% capacity; top
charge-quartile occupancy moved 0.008 → 0.007. EXP-017 raised the threshold to
75% and 85%; occupancy moved to 0.049 while the skill gradient collapsed from
2.1x to 0.9x.

Three separate attempts failed to make the player *choose* to sit near overload.
The asymmetry is structural: the downside is losing the run, the upside is a
marginal tempo gain. No rational agent takes that trade, and no threshold
tuning changes the shape of it.

> **Principle**: a resource cannot be made dangerous by rewarding the player for
> carrying it. It becomes dangerous only when something else *forces* it on
> them faster than they can spend it. Design the pressure, not the incentive.

**Correction, EXP-029.** The evidence above came from an agent whose evaluation
function contained an explicit `-25 per point of headroom below 4` fear term —
we were measuring danger-avoidance with an instrument told to avoid danger. An
optimizer with a purely outcome-based evaluation occupies the top charge
quartile **12.5%** of turns and plays near overload **9.1%** of turns, against
3.0% and 2.5% for the biased one: a 3.6x difference.

The principle survives and is arguably strengthened — the neutral agent lives
near the brink on `surge`, which pushes charge onto the player, and *not at all*
on drone-only `swarm` (0.0%), which is exactly "pressure, not incentive". But
the absolute claim that nothing can make the player approach overload was too
strong, and part of the reason it looked airtight was us.

### D-009 — In a conserved economy, damage is self-limiting

**Evidence**: EXP-018 scaled enemy shove strength 1x → 3x. Player near-overload
time went **down**, 3.6% → 0.9%, and the optimizer's death rate fell.

If attacking means transferring your own resource, then an enemy that hits hard
empties itself in one blow. Big hitters disarm themselves. This is a genuinely
pleasant property — you can never be burst down out of nowhere — but it means
the obvious lever for "make the player feel pressure" points the wrong way.

### D-010 — ~~Conservation permits a stable charge oscillation~~ **FALSIFIED**

**Original claim**: timeout rate is 36-37% at every turn limit from 45 to 120,
therefore two adjacent units must be passing the same charge back and forth in a
fixed point that time cannot break.

**Disproof**: EXP-020 (make transfers lossy) and EXP-021 (forbid the immediate
reply) both attacked that oscillation and both made timeouts *worse*. Then a
trace of a deadlocked board (seed 1000, turns 37-45) showed nothing moving at
all — no exchanges were happening. The observation was right and the mechanism
was invented. See D-012 for what is actually going on.

**Kept as a correction, not deleted.** Two rules were designed and tested
against a mechanism nobody had looked at, and the cost was a whole batch. The
turn-limit invariance was real evidence of *a* fixed point; naming which fixed
point required opening the board.

### D-011 — Adding reach to a verb can subtract tension

**Evidence**: EXP-019 made `SHOVE` displace the body it hits. The optimizer's
death rate halved (19% → 8.5%), greedy nearly tripled (12.5% → 30.5%), the
gradient narrowed, and the deadlock got worse (39% → 49% timeouts).

It was proposed as an offensive tool (herd enemies onto piles) and behaved as a
defensive one (push the problem away). A verb that lets the player *reset* a
bad position is worth more to the player than the same verb used aggressively —
so it flattens the difference between good and bad positioning.

> **Principle**: before adding an ability, ask what it does for the player who
> is losing. That is usually what it will actually be used for.

### D-012 — The deadlock was a traffic jam, and spent bodies were the cause

**Evidence**: trace of seed 1000, turns 37-45: `DRO4/6 SIP9/14 DRO5/6 WAR8/10
DRO5/6 DRO2/6 . DRO0/6 YOU5/10 . SIP10/14 WAR9/10` — nine units on twelve
nodes, every action `end turn`, nothing moving for nine consecutive rounds.
Removing spent units (EXP-022) took timeouts 40.8% → 20.0%; adding nodes
instead (EXP-023) changed nothing.

Bodies block absolutely, so as unit count approaches node count the ring
freezes. Chasers queue behind each other and the ones at the back can never
reach anything. Worst of all, a chaser that has shoved its last charge is
harmless *and permanent* — it can never be killed, because killing means
overfilling and nobody has a reason to spend charge on a threat that is already
neutralised. The encounter's win condition then cannot be met.

The fix was already implied by the model: a unit holding no charge holds
nothing, so removing it costs conservation exactly zero.

> **Principle**: in a game where bodies occupy space, ask what happens to the
> ones that stop being threats. If they neither leave nor can be removed, they
> are furniture, and enough furniture is a deadlock. And note the shape of the
> error: adding space (D-023) treats the symptom, removing the dead treats the
> cause.

### D-013 — A correctly killed mechanic can become correct later

**Evidence**: `hungryEnemies` was killed in EXP-007 (timeouts 69.6% → 86.0%,
skill gradient 5.1x → 1.1x). Resurrected unchanged in EXP-025 it took the
turtle agent on `swarm` from 99% to 28% and *raised* tip kills from 4.38 to
5.04.

Nothing about the rule changed. Its world did. In EXP-007 the floor **killed**,
so foragers suicided into piles and unskilled agents got free kills. Under
`absorbCap` the floor **loads**, so a forager fills to capacity and survives —
doing the player's setup work for them and arriving hot-and-brittle.

> **Principle**: graveyard entries should record the *conditions* a mechanic
> failed under, not just the verdict. A rule that fails is often a rule whose
> preconditions are absent. Re-read the graveyard whenever a precondition
> changes.

### D-014 — Replicate across shapes before adopting, or you will ship a walkover

**Evidence**: dissolution looked like an unambiguous win on `surge` (timeouts
40.8% → 20.0%, every secondary metric up). On drone-only `swarm` the same rule
took the do-nothing agent to **99%**.

One encounter shape is one sample. The failure was not subtle — it was total —
and it was invisible on the shape the rule was developed against.

> **Principle**: a rule is adopted against the *panel of encounters*, never
> against the one you were looking at. Cheap to run, and it caught a degenerate
> walkover that would otherwise have become the baseline.

### D-015 — A design metric can be dominated by causes that are not design

**Evidence**: the 40.8% deadlock decomposed as ~16pp traffic jam (design),
~13pp enemy-AI bugs, ~7pp search horizon, ~5pp genuinely unresolvable.

We spent two batches proposing *rules* to fix a number that was 60% engine bugs
and agent myopia. The two AI bugs were mundane — a blocked unit reversing
direction into a stable two-cycle, and a full scavenger burning its action on an
absorb that took nothing — and neither is visible in any aggregate. Both were
obvious within thirty seconds of reading a board.

> **Principle**: before treating a metric as a design signal, decompose it.
> A number that has not been separated into design / correctness / instrument
> is not evidence about the design.

### D-016 — Your evaluation function is part of the experiment

**Evidence**: EXP-029 — removing one fear term from the agent's evaluation
changed near-overload play by 3.6x and flipped the result on one encounter
(`swarm`: 79% → 99%). EXP-027 — *adding* a plausible, strategy-neutral
distance-to-goal term collapsed the same agent from 78% to 29% by paying it to
load enemies without finishing them.

An agent's evaluation function is not a neutral window onto the game. It encodes
beliefs, and any claim about player behaviour is a claim about *that agent's*
behaviour until checked against a different one.

> **Principle**: keep at least two instruments with different evaluations and
> report both. And never add a heuristic term to fix a measurement — in a game
> where being closer to a goal can be more dangerous than being far from it,
> "distance to goal" is not monotone and will be exploited.

### D-017 — Four rule experiments failed where one archetype succeeded

**Evidence**: EXP-008, 015, 017 and dissolution's side effect all failed to move
the player's top-quartile charge occupancy off ~3%. Adding a single enemy type
moved it to 29.6%, and on that encounter the agent *without* a fear-of-overload
term beats the one with it (57.8% vs 52.5%) while spending 31.8% of turns near
overload against 5.9%.

D-008 concluded "design the pressure, not the incentive" and we then spent four
experiments looking for that pressure in the **rules**. It was never going to be
there. Pressure is a property of what the player is fighting, not of what the
verbs do.

> **Principle**: when a desired player behaviour resists several rule changes,
> check whether it is a *content* question before writing a fifth rule. Rules
> define what is possible; content decides what is forced.

### D-018 — Geometry caps pressure, and no amount of tuning lifts the cap

**Evidence**: on a 12-node ring with one unit per node, melee pressure is capped
three independent ways — at most two units can be adjacent to the player; a hard
hitter empties itself in one blow (D-009); and the player moves 2-3 nodes a turn
against an enemy's 1, so they can always kite. EXP-018's throughput sweep
(1x → 3x) *reduced* player danger. The lobber lifts the cap only because it
reaches over the front rank.

> **Principle**: before tuning a pressure number, compute the structural ceiling
> the board imposes on it. If the geometry caps incoming pressure at two
> attackers, no per-attacker number reaches a third.

Note the corollary that keeps the lobber honest: it cannot throw at range 1, so
the counter is positional rather than statistical. The measured behaviour shows
the counter is real but expensive — the strong agent closes to range 1 only
14.4% of turns and spends 69.6% inside the threatened band, because closing on
one lobber exposes it to the others.
