# GRAVEYARD.md

Killed and archived work, with enough detail that we do not rediscover it.

---

### Floor-scattered wave charge — **KILLED**

*Intuition*: raise the energy budget (EXP-013 proved it was the binding
constraint) by scattering charge onto the ring as waves arrive.
*What failed*: the turtle agent went to **73% win with a 0% death rate**. Ambient
charge plus enemies that absorb on contact means the board kills for you; the
optimal play became standing still. Any charge the player did not place is a
free weapon.
*Salvaged*: the escalation goal was right. Injecting the same charge **inside
enemy bodies** (encounter `surge`) kept the ramp and killed the exploit — and
gave a better curve, since late enemies arrive hot *and* brittle.
*Revisit if*: absorption is ever made deliberate rather than automatic.

### `hungryEnemies` — spent chasers forage — **KILLED (EXP-007), then RESURRECTED (EXP-025)**

> **Status: alive again, unchanged, and now a default.** See the note at the end
> of this entry. This is the entry that justifies keeping a graveyard.

*Intuition*: D-001 said a conserved economy needs circulation; empty enemies
were inert furniture.
*What failed*: timeouts went **up** (69.6% → 86.0%) and the skill gradient
collapsed from 5.1x to 1.1x. Foragers eat the charge the player is staging, so
mine-building becomes unreliable, while dumb agents benefit from enemies
suiciding into random piles. It helped exactly the agents it should have hurt.
*Salvaged*: nothing, at the time. The circulation diagnosis was itself wrong —
the real constraint was the energy budget (EXP-013).

*Conditions under which it might become viable* (written at kill time, and this
is the part that paid off): "if enemies can no longer kill themselves on loose
charge". That is exactly what `absorbCap` (EXP-014) did. Under v0.6 a forager
fills to capacity and **survives**, arriving hot-and-brittle — it stages the
player's kill instead of stealing it. Resurrected in EXP-025 with no change to
the rule at all: turtle on `swarm` 99% → 28%, tip kills 4.38 → 5.04. See D-013.
Known cost: it punishes the middle of the skill ladder hardest (miner 31% → 17%
on `surge`), which is now Q7.

### `settleMotes` — charge under a body is absorbed at end of round — **KILLED** (EXP-008)

*Intuition*: venting is a free safety valve (D-002), so make putting charge down
a positioning problem.
*What failed*: optimizer 30.4% → 6.4% and the danger band **did not move at all**
(top-quartile occupancy 0.1% before and after). It closed the `dir = 0` valve
while leaving the sideways one wide open, so it cost the player their staging
area and bought nothing.
*Revisit if*: shoving is ever restricted to occupied nodes.

### Higher hot thresholds (0.75, 0.85) — **ARCHIVED** (EXP-017)

Raising the threshold to force the player higher up the charge band moved the
player's occupancy by 0.7pp — and made *enemies* hot far less often, so greedy
jumped from 18% to 42.5% and the gradient collapsed. The threshold is an enemy
difficulty dial wearing a player-tension costume.

### Enemy throughput as a danger lever — **ARCHIVED as a danger lever** (EXP-018)

Scaling enemy shove strength 1x → 3x *reduced* player near-overload time from
3.6% to 0.9%. In a conserved economy a hard hit is also a full disarm, so
heavy hitters neutralise themselves. Kept at 1.5x purely because it widens the
skill gradient (2.1x → 3.4x), which is a different justification from the one we
went looking for.

### `shovePushes` — shoving displaces the body — **ARCHIVED** (EXP-019)

*Intuition*: break the two-body deadlock and let the player herd enemies onto
piles.
*What happened*: it did not touch the deadlock (optimizer timeouts 39% → 49%)
and turned out to be primarily a *defensive* tool — the optimizer's death rate
halved to 8.5% and greedy jumped to 30.5%, narrowing the gradient. Adding reach
to a verb subtracted tension.
*Revisit if*: we want a deliberately safer, more puzzle-like variant, or if
displacement is made costly.

### `spillFraction` — transfers leak onto the floor — **KILLED** (EXP-020)

*Intuition*: D-010 said the deadlock was a charge oscillation, so make exchanges
non-undoable.
*What failed*: timeouts rose (40.8% → 45.2%), and at spill 0.5 the game stopped
completely — every agent 100% timeout, zero detonations.
*Two separate errors, both worth remembering*: the diagnosis was invented rather
than observed (D-010 is now marked falsified), and the implementation was
dodgeable — `floor(amount × fraction)` means a shove of 1 spills nothing, and
the agents immediately switched to shoving 1s. We measured our own loophole.
*Revisit if*: a flat per-action spill is ever wanted as an economy tax, for a
reason other than the deadlock.

### `staggerOnShove` — no immediate reply — **KILLED** (EXP-021)

Same wrong diagnosis, same direction of failure: timeouts 40.8% → 57.6%,
optimizer win halved. Both this and spill reduce the rate at which charge gets
*delivered*, and delivery is what ends encounters. Two independently motivated
fixes failing identically is the tell that the model is wrong — that is when we
stopped writing rules and traced a deadlocked board.

### Ring size as a deadlock fix — **KILLED** (EXP-023)

Enlarging the ring from 12 to 16 or 20 nodes moved timeouts by 3pp and 20 was
*worse* than 12. Chasers pack against the player wherever the player is, so
extra nodes add empty ring behind the queue, not room inside it. Valuable as the
control that ruled out "just add space" and isolated dissolution as the real fix.

### Distance-to-goal evaluation term — **KILLED** (EXP-027)

*Intuition*: a 2-ply search can never see a kill that needs 15 charge delivered,
so partial progress scores as pure loss. Give the agent the win condition's own
distance metric — total charge still needed to clear the board. Strategy-neutral
by construction, and the textbook fix for the horizon effect.
*What failed*: catastrophically. Timeouts 10.3% → **67.3%**, win 78.0% → 29.0%,
tip kills halved. Rewarding "closer to clearing" pays the agent for *loading*
enemies without finishing them, because a nearly-full enemy scores almost as
well as a dead one. It hoards, parks at 25-50% capacity, and stops killing.
*The general lesson*: a distance-to-goal heuristic is only safe when being
closer is monotonically better. Here a nearly-full enemy is **more dangerous**
than an empty one, so the metric is not monotone and the search exploits it.
*Salvaged*: the underlying diagnosis was right — the residual really was myopia.
Deepening the search from 2 to 3 actions fixed it properly (12.0% → 5.0%)
without touching the evaluation. Fix the horizon, not the scoring.

### `bomber` agent — **KILLED**

A badly specified "commit to one strategy" agent: 0% win, 19% death. Its pile
placement aimed at where a scavenger *was*, not where it would *go*. Replaced by
`miner`, which predicts movement. Kept as a reminder that a weak result from a
weak agent is not evidence about the game.

### The original `baitKills` metric — **SUPERSEDED**

First definition counted any enemy that had ever eaten a player-placed mote and
later died. Tightened mid-batch to "the same absorption took it over capacity",
which *raised* confidence in the finding rather than lowering it (2.92 → 2.70 of
3.63 kills). Made obsolete entirely by `absorbCap`, which makes floor kills
impossible by construction; its successor is `tipKills` — a kill by player shove
on a target the player had fattened first.
