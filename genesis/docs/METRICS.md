# METRICS.md

Definitions only. **Metrics identify candidates for inspection. They do not
define fun.** Anything on this list that stops changing a decision gets deleted.

## Outcome
- `winRate` — encounters cleared / encounters played.
- `turns` — mean turns to resolution.
- `deathCause` — `overload` | `timeout`.

## Decision quality
- `actionEntropy` — Shannon entropy (bits) over the chosen action *type*
  (`step`, `shove`, `end`). Max = log2(3) ≈ 1.585.
- `shoveEntropy` — entropy over the chosen shove *amount* (1..throughput).
  **Collapse toward 0 is the alarm**: it means the "how much" decision is fake.
- `conditionalShoveEntropy` — shove-amount entropy computed *within* player
  charge-band buckets, then averaged. High global entropy with low conditional
  entropy = good (context-sensitive), the target of rule 20. Both high = maybe
  just noise. Both low = fake decision.
- `unchosen` — legal actions never selected across a batch. Dead options.

## The core tension
- `chargeBand` — fraction of player-turns spent in each quartile of capacity.
  A healthy core should show the player *moving through* bands, not parking.
- `nearOverload` — player-turns at ≥ 90% capacity. The "chicken" statistic.
- `feedRatio` — charge shoved into enemies / total charge shoved. Low means
  players are using SHOVE as a vent, not a weapon.

## Emergence
- `chainHistogram` — detonations resolved per cascade. Length ≥ 2 = a chain.
- `selfDetonations` — player overloads (only reachable in burnout mode).
- `baitKills` — enemies destroyed by absorbing motes the player placed.
  This is the "the board is a weapon" metric; it is the one we most want to see.

## Correctness (not design)
- `conservationViolations` — must be 0. Asserted per transition.
- `cascadeOverflow` — cascades hitting the 64-detonation guard. Must be 0.

---

## Sample size

At the win rates this project works in (20-60%), 150 seeds gives roughly ±8pp on
a single arm and **±11pp on the difference between two arms**. A 10pp delta at
150 seeds is not a result.

EXP-040 nearly recorded a false finding on exactly this: a 150-seed pass showed
one flag raising the mid-rung more than the top, and 350 seeds showed the
opposite. Standing rule: **confirm any surprising delta at 300+ seeds before
building on it**, and quote the seed count next to every number.
