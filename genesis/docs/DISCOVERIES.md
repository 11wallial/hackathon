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

### D-009 — In a conserved economy, damage is self-limiting

**Evidence**: EXP-018 scaled enemy shove strength 1x → 3x. Player near-overload
time went **down**, 3.6% → 0.9%, and the optimizer's death rate fell.

If attacking means transferring your own resource, then an enemy that hits hard
empties itself in one blow. Big hitters disarm themselves. This is a genuinely
pleasant property — you can never be burst down out of nowhere — but it means
the obvious lever for "make the player feel pressure" points the wrong way.

### D-010 — Conservation permits a stable deadlock that time cannot break

**Evidence**: timeout rate is **36-37% at every turn limit from 45 to 120**.

Two adjacent units with charge can pass the same charge back and forth forever;
each transfer is exactly undone by the reply. Because nothing decays and nothing
is created, this is a genuine fixed point. Raising the turn limit changes only
how long the player watches it.

> **Principle**: a conserved system needs at least one *irreversible* move, or
> some states are unreachable from others and the game cannot be finished.
> This is the same insight as D-001 arriving from the other side: conservation
> forbids explosions and climaxes alike, and you have to put one back.

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
