# DESIGN_THESIS.md

> Current belief about what makes this game interesting. **Not scripture.**
> Revised when evidence contradicts it. Revision log at the bottom.

## v0.1 — 2026-09-13 (pre-evidence, written before any code ran)

### The one-sentence thesis

**Charge is simultaneously your ammunition, your power level, and your death
clock — and the total amount of charge in a fight is conserved.**

### Why we think that is a good bet

Most action-roguelike combat separates three quantities: a *resource* you spend
(mana/energy), a *power* stat, and a *health* pool that only ever goes down.
Each is a separate dial, and each is independently inflatable, which is why
escalation in the genre usually degenerates into bigger numbers.

We collapse all three into one integer per unit, `charge`, with two rules:

1. **Overload, not depletion.** A unit is destroyed when its charge *exceeds*
   its capacity. Being full is lethal; being empty is merely helpless.
2. **Conservation.** Charge is never created or destroyed inside an encounter.
   Every point you spend arrives somewhere: in an enemy, or on the floor.

From those two rules alone, several tensions should appear *without us
designing them separately*:

| Tension | Where it comes from |
|---|---|
| greed vs survival | holding charge = power, but also proximity to overload |
| attack vs arm-the-enemy | damage *is* giving the enemy your resource |
| kill timing | a kill dumps the victim's charge into its neighbourhood — including you |
| positioning = economy | charge on the floor is picked up by walking over it |
| denial | the floor is a shared bank; enemies can withdraw from it |

### The three mechanics (and nothing else, yet)

1. **Charge / capacity / overload** (the collapse described above)
2. **The ring**: a closed 12-node loop. One unit per node, so bodies block.
   Loose charge ("motes") sits on nodes.
3. **Two verbs**: `STEP` (move one node, absorb every mote there) and
   `SHOVE` (push up to `throughput` charge into an adjacent node — or your own).
   If a unit is there it absorbs; otherwise the charge lands as motes.

That is the whole game. Everything else must be *earned by evidence*.

### Deliberate consequences we are betting on

- **`SHOVE` is one verb doing four jobs**: attack, self-vent, mote placement,
  and bait-laying. High mechanical leverage per rule.
- **Auto-absorb applies to enemies too.** A pile you leave on the floor is a
  landmine for a greedy enemy. Failure states (spilled charge) become weapons.
- **Escalation = more total charge in the system**, not more enemy HP. A late
  fight is faster and more explosive, not spongier.
- **No infinite economies are possible.** Conservation is a hard invariant, so
  the classic roguelike degenerate loop (resource-positive cycle) cannot exist
  by construction. We assert this as a *testable* property, not a hope.

### The counterpressure hypothesis (the load-bearing one)

If attacking were purely good, `SHOVE max at nearest enemy` would dominate.
The intended counterpressure is the **hot rule**: a unit at ≥50% capacity takes
two actions per turn instead of one. So feeding an enemy makes it *more
dangerous before it pops*. Every attack is therefore a bet: *do I have enough
throughput to push it over the line, or am I just making it angry?*

**If the hot rule is not carrying that weight, the core is broken.** EXP-002
is designed to falsify this.

### What would make us abandon this thesis

- Optimising agents converge on one shove amount across all contexts.
- Chain detonations either never happen or happen uncontrollably (i.e. they are
  randomness, not agency).
- The safe-charge band turns out to be a single number the player parks on.

### Similarity risk note

*Shared/conserved resource*: some card games use shared mana pools; we are not
aware of an action-roguelike whose combat is a zero-sum shoving match over a
fixed quantity. *Overload-as-death*: precedent exists for "heat" systems, but
those are usually a second bar alongside HP, not a replacement for it.
*Chain detonation*: widespread; our version is distinct only because the payload
is conserved and player-placed. Abstract principle we are reusing: "make the
player's resource and the enemy's threat the same object." Our new affordance:
the floor as a public, stealable, weaponisable bank.

---

## Revision log

### R1 — 2026-09-13, after batch 1 (EXP-001..006)

**What survived.** The skill gradient is real (optimizer 45% vs random 1.7% on
identical seeds). Conservation held exactly and bought us immunity to
resource-positive degeneracy. The hot rule is load-bearing. Burnout overload
earned its place and is now the default.

**What was wrong.**

1. *"Charge is your death clock."* — **Falsified in practice.** The player
   spends 0.1% of turns in the top charge quartile. Venting is free, so the
   danger is opt-out. The thesis is not wrong in principle, it is
   **unimplemented**: nothing forces you to hold charge you do not want.

2. *"Escalation = more charge in the system."* — **Falsified.** A closed system
   runs *down*, not up. 55-96% of encounters reached the turn limit with both
   sides too drained to threaten each other. Conservation without circulation
   produces heat death, not climax.

3. *"SHOVE is the attack; the floor is a side effect."* — **Inverted by the
   evidence.** 74% of the winning agent's kills come from enemies eating
   player-placed piles. Direct attack is the weak line.

**Revised thesis (v0.2).**

> **You fight by putting your own power on the floor in front of things that
> eat.** Charge is the same object as your ammunition, your power, and your
> risk — and the way you deal damage is to *let go of it* somewhere an enemy
> will walk. Everything on the board is hungry, including you.

That reframing makes three previously separate rules into one idea: the floor
is a shared, contested bank; absorbing is universal and automatic; and a pile
is simultaneously a discard, a weapon, a bait, and a loan to whoever reaches it
first. It also tells us exactly what is missing: **enemies must stay hungry**
(or the board stops circulating) and **the player must not be able to put
charge down for free** (or the risk half of the thesis never happens).

Batch 2 is built to test precisely those two, plus the arithmetic fix that
makes chains reachable at all.

### R2 — 2026-09-13, after batches 2-5 (EXP-007..019)

**Thesis v0.3.** Two more claims fell, and one got much sharper.

*Fell*: "the player's charge is a death clock they must manage" — EXP-008, 015
and 017 all failed to make the player occupy the dangerous band, and D-008
explains why no incentive ever will. This is now Q1, a decision rather than a
tuning problem. Also fell: "harder-hitting enemies create pressure" (D-009,
damage is self-limiting under conservation).

*Sharpened*: the floor. What v0.1 found by accident (D-003, mines) and what
v0.5 turned it into (`absorbCap`: the floor *loads*, you *kill*) is the same
idea at two strengths, and the stronger version fixed the worst exploit in the
project without losing the tactic.

> **Thesis v0.3.** Charge is a single finite thing that is ammunition, power and
> mortality at once, and it only ever changes hands. You do not damage an enemy
> — you **overfill** it, which means the way to kill something is to arrange for
> it to receive more than it can hold. The floor is the shared, contested bank
> everything draws from; loading a target from it is free, but the last point
> has to come from you. Escalation is not bigger enemies, it is a denser field:
> later arrivals come in nearly full, which makes them dangerous and brittle at
> the same time.

The unfinished sentence in that thesis is the player's own capacity. Right now
it is a wall they stand well clear of, not a clock. Q1 decides whether we find
the pressure that makes it a clock, or move that tension onto the enemies and
say so honestly.
