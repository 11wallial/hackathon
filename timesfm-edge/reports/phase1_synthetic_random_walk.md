# Phase 1 report: synthetic_random_walk

Generated 2026-09-06T08:00:01.196155+00:00. Config hash `f01163c98e74`.

**Verdict: `STOP`**  (Test A FAIL, Test A at 2x costs FAIL, Test B FAIL)

- adjusted lower bound 0.4964 vs break-even 0.7487 (1x) / 0.9975 (2x): fails 1x, fails 2x
- hit rate 0.5024 vs last_sign 0.4952: beats
- hit rate 0.5024 vs best constant sign 0.5046: does not beat
- mean abs coverage error 0.0277 (limit 0.05): ok
- pinball 0.001165 vs garch 0.001151, ewma 0.001152: does not beat both

## Setup

- Data: `synthetic` random_walk 1h bars, 20000 bars from 2022-01-01 00:00:00+00:00 to 2024-04-13 07:00:00+00:00
- Candidate: `ar1` model `-` input `log_price` context 512 horizon 1 bar(s)
- Walk-forward: 8 forward-chained folds, purge = horizon, embargo 24 bars, 16998 out-of-sample decision points
- Costs (per side bps): commission 5.0, half-spread 0.5, slippage 2.0; round trip 15.0 bps (1x), 30.0 bps (2x)
- Mean |tradable 1-bar return|: 30.2 bps
- **Break-even hit rate: 0.7487 (1x), 0.9975 (2x)**
- **Configuration variants in ledger (N for adjustment): 1**; this run's adjusted alpha = 0.05/1 = 0.05000
- Ledger-wide survivors: Holm 0, BH 0 of 1 variants with p-values

## Test A: directional edge (tradable open-to-open return)

| forecaster | n | hit rate | 95% CI | adj. lower bound | p (one-sided) | IC (Spearman) | IC 95% CI | trade frac | net/bar 1x (bps) | Sharpe 1x | net/bar 2x (bps) | Sharpe 2x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ar1 (candidate)** | 16998 | 0.5024 | [0.4952, 0.5099] | 0.4964 | 0.2611 | -0.0066 | [-0.0204, 0.0080] | 1.00 | -14.77 | -35.68 | -29.77 | -71.91 |
| zero | 0 | nan | [nan, nan] | nan | nan | nan | [nan, nan] | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| last_sign | 16998 | 0.4952 | [0.4872, 0.5026] | 0.4886 | 0.8890 | -0.0110 | [-0.0253, 0.0033] | 1.00 | -15.40 | -37.21 | -30.40 | -73.44 |
| ewma | 0 | nan | [nan, nan] | nan | nan | nan | [nan, nan] | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| garch | 0 | nan | [nan, nan] | nan | nan | nan | [nan, nan] | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Best constant-sign rate (always long or always short): 0.5046. Break-even: 0.7487 (1x) / 0.9975 (2x).

Same statistics on the forecast target (close-to-close), for reference only; you cannot trade this:

| forecaster | hit rate cc | 95% CI | IC cc |
|---|---|---|---|
| **ar1 (candidate)** | 0.5014 | [0.4938, 0.5085] | -0.0076 |
| zero | nan | [nan, nan] | nan |
| last_sign | 0.4964 | [0.4888, 0.5041] | -0.0123 |
| ewma | nan | [nan, nan] | nan |
| garch | nan | [nan, nan] | nan |

### Per-fold candidate hit rate (tradable)

| fold | n | hit rate | mean net/bar 1x (bps) |
|---|---|---|---|
| 0 | 2125 | 0.5040 | -15.39 |
| 1 | 2125 | 0.4885 | -16.14 |
| 2 | 2125 | 0.5078 | -14.06 |
| 3 | 2125 | 0.5087 | -13.93 |
| 4 | 2125 | 0.5054 | -15.16 |
| 5 | 2125 | 0.5139 | -13.70 |
| 6 | 2124 | 0.4920 | -15.21 |
| 7 | 2124 | 0.4991 | -14.57 |

## Test B: calibration (forecast target, close-to-close)

| forecaster | 20% cov | 40% cov | 60% cov | 80% cov | mean abs cov err | pinball (mean, 1e-4) | CRPS proxy (1e-4) |
|---|---|---|---|---|---|---|---|
| **ar1 (candidate)** | 0.216 | 0.434 | 0.637 | 0.824 | 0.0277 | 11.6535 | 23.3070 |
| zero | 0.217 | 0.432 | 0.637 | 0.824 | 0.0275 | 11.6532 | 23.3065 |
| last_sign | 0.146 | 0.302 | 0.478 | 0.685 | 0.0975 | 15.3845 | 30.7690 |
| ewma | 0.191 | 0.387 | 0.589 | 0.792 | 0.0105 | 11.5222 | 23.0443 |
| garch | 0.195 | 0.395 | 0.596 | 0.802 | 0.0042 | 11.5084 | 23.0167 |

Per-quantile empirical coverage P(y <= q_level):

| forecaster | q0.1 | q0.2 | q0.3 | q0.4 | q0.5 | q0.6 | q0.7 | q0.8 | q0.9 |
|---|---|---|---|---|---|---|---|---|---|
| **ar1 (candidate)** | 0.087 | 0.183 | 0.285 | 0.393 | 0.498 | 0.609 | 0.718 | 0.820 | 0.911 |
| zero | 0.089 | 0.186 | 0.290 | 0.397 | 0.504 | 0.614 | 0.722 | 0.823 | 0.913 |
| last_sign | 0.160 | 0.263 | 0.350 | 0.429 | 0.501 | 0.575 | 0.652 | 0.740 | 0.844 |
| ewma | 0.107 | 0.210 | 0.312 | 0.410 | 0.504 | 0.601 | 0.699 | 0.799 | 0.899 |
| garch | 0.102 | 0.206 | 0.308 | 0.408 | 0.504 | 0.603 | 0.702 | 0.803 | 0.904 |

![reliability](reliability_synthetic_random_walk.png)

## What would have to be true for a positive result here to be spurious

1. **A leak survived the tests.** `tests/test_no_lookahead.py` shifts labels and checks the
   harness catches it, but a leak in the *data feed* (e.g. a venue that restates closes, or a
   CSV with close-timestamps mislabelled as opens) is invisible to those tests. Verify the
   feed's timestamp convention by hand against a second source.
2. **Selection across the ledger.** The Bonferroni bound only covers variants recorded in
   `experiment_ledger.json`. Any variant tried elsewhere (a notebook, a deleted ledger, a
   different repo) is uncounted and the true N is larger.
3. **Regime luck.** 8 forward-chained folds over 2.3 years is still one draw of
   history. A hit rate that comes from two folds and is flat elsewhere is a regime, not an edge.
   Check the per-fold table below.
4. **Cost model too kind.** Costs assume small size and passive fills at the open. If real
   fills are worse than the 2x row, the 2x row is the optimistic one.
5. **|move| is not independent of correctness.** The break-even formula assumes it is. If the
   model is wrong mostly on large moves (typical: it is slow to react to jumps), the true
   break-even hit rate is above the number printed here.
6. **Bootstrap block length too short.** Blocks of 26 bars may not span the
   dependence in hourly crypto vol clusters; a longer block widens the interval.

## Assumptions most likely to be wrong

- Execution at the next bar's open at the assumed cost; no partial fills, no funding payments (perpetuals pay funding every 8h, which is a further cost or income the model ignores).
- Costs are constant. Spread and slippage widen exactly when volatility spikes, which is also when |return| and therefore apparent 'edge' are largest.
- |realised move| is independent of forecast correctness (used in the break-even formula). Usually false; errors cluster on large moves.
- Bars from a single venue represent the price you could trade at. Cross-venue arbitrage bots make the printed close a stale number by the next open.
- The circular block bootstrap block length (n^(1/3), at least H) spans the serial dependence. Volatility clustering in hourly crypto can persist for days.
- The multiple-testing count only includes variants recorded in the ledger. Anything tried outside this harness is uncounted.
- TimesFM's normalisation and detrending (RevIN, linear detrending in 3.0) is well-behaved on log-price inputs; a level-input forecast that mostly extrapolates the local slope is a momentum proxy, not a new signal.
- For horizon > 1 in log_return mode, multi-step quantile spreads are combined assuming independent steps.
- GARCH baseline is fitted once per fold and filtered forward; a practitioner would refit daily and do slightly better, so the calibration bar is slightly too low.
- Synthetic validation series are Gaussian-GARCH; real returns have jumps and fat tails that neither the AR(1) nor the vol baselines capture, which cuts both ways.
