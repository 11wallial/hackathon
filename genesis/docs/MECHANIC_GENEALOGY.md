# MECHANIC_GENEALOGY.md

Where each surviving mechanic came from, what it was trying to solve, and what
happened to it.

```
                    "collapse resource + power + health into one integer"
                                        │
                    ┌───────────────────┴───────────────────┐
            CHARGE / OVERLOAD                          CONSERVATION
          (die when over capacity)              (nothing created or destroyed)
                    │                                       │
       ┌────────────┼────────────┐              ┌───────────┴───────────┐
    HOT RULE   BURNOUT      THE FLOOR        no infinite          heat death
   (EXP-002)  (EXP-003)   (loose charge)      economies            (D-001)
       │           │             │           (EXP-006, kept)           │
       │           │             │                                     │
       │           │      ┌──────┴───────┐                    energy budget
       │           │   BAIT KILLS    ABSORB CAP                 (EXP-013)
       │           │   (D-003, the      (EXP-014)                     │
       │           │    accident)           │                   charge arrives
       │           │        │               │                   inside bodies
       │           │        └──── became ───┤                    (encounter
       │           │                        │                      `surge`)
       │           │                    TIP KILLS
       │           │              "load them, then tip them"
       │           │
       │      self-detonation as an offensive move (D-005)
       │
    decides whether skill matters at all (D-004)
```

## Entries

**CHARGE / OVERLOAD** — origin: the founding idea, that a single integer can be
ammunition, power and health at once. Problem it solves: escalation in this
genre degenerates into number inflation because those three quantities are
separate dials. Mutations tested: lethal vs burnout overload (EXP-003, burnout
won). Status: foundational, unchallenged.

**CONSERVATION** — origin: same founding idea, taken seriously. Solves resource
degeneracy permanently (EXP-006). Cost discovered later: it also forbids climax
(D-001) and permits deadlock (D-010). Combines with: everything; it is the
reason the floor is interesting and the reason kills fund the next kill.

**THE HOT RULE** — origin: designed as counterpressure against "always shove
maximum". Turned out not to shape expert behaviour at all; what it actually does
is decide whether being unsophisticated is punished (D-004). Mutations: threshold
0.5 / 0.75 / 0.85 (EXP-017 — 0.5 won); symmetric player bonus (EXP-015, kept for
its effect on the gradient, rejected as a fix for Q1). Status: load-bearing for
the reason we did not predict.

**BURNOUT** — origin: a softer alternative to instant death. Became something
better: because the blast still happens, self-immolation is a *tactic* the
searching agent adopts unprompted (D-005). Combines with: chains, and with the
floor (your own corpse's payload is recoverable).

**THE FLOOR / BAIT** — origin: a side effect. `SHOVE` had to put charge
*somewhere* when there was no target. Became the strongest strategy in v0.1
(D-003) — 74% of the winning agent's kills. Mutated by `absorbCap` (EXP-014)
from "the floor kills" into "the floor loads, you kill", which fixed the
do-nothing exploit (D-007) without losing the tactic. Signature line: **salt the
retreat** — step away from a chaser and mine the tile you just left.

**TIP KILLS** — origin: the direct descendant of bait under `absorbCap`. Fatten
a target from the floor until it is hot-and-brittle, then tip it over with a
small shove. Currently 3.6 of the optimizer's 9.1 kills per run. This is the
mechanic the game is currently *about*.

## Similarity risk

The distinctive combination here is conservation + overload-as-death + a public
floor that everything eats from. Individually each has precedent (heat systems,
shared resources, ground-based pickups); we are not aware of a tactics game
where attacking means transferring your own finite resource into the thing you
are attacking, and where the floor is a contested bank that arms both sides.
The riskiest single element is the ring-with-blocking-bodies, which is common
geometry — but it is doing unusual work here, because a body that cannot be
passed is also a body that must walk through whatever you left behind.
