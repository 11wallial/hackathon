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

### `hungryEnemies` — spent chasers forage — **KILLED** (EXP-007)

*Intuition*: D-001 said a conserved economy needs circulation; empty enemies
were inert furniture.
*What failed*: timeouts went **up** (69.6% → 86.0%) and the skill gradient
collapsed from 5.1x to 1.1x. Foragers eat the charge the player is staging, so
mine-building becomes unreliable, while dumb agents benefit from enemies
suiciding into random piles. It helped exactly the agents it should have hurt.
*Salvaged*: nothing directly. The circulation diagnosis was itself wrong — the
real constraint was the energy budget (EXP-013).

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
