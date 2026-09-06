# Phase 1 report: synthetic_ar1_phi015

Generated 2026-09-06T08:00:44.446680+00:00. Config hash `fde2de1b84b5`.

**Verdict: `STOP`**  (Test A FAIL, Test A at 2x costs FAIL, Test B FAIL)

- adjusted lower bound 0.5400 vs break-even 0.7378 (1x) / 0.9757 (2x): fails 1x, fails 2x
- hit rate 0.5477 vs last_sign 0.5504: does not beat
- hit rate 0.5477 vs best constant sign 0.5083: beats
- mean abs coverage error 0.0358 (limit 0.05): ok
- pinball 0.001215 vs garch 0.001207, ewma 0.001209: does not beat both

## Setup

- Data: `synthetic` ar1 1h bars, 20000 bars from 2022-01-01 00:00:00+00:00 to 2024-04-13 07:00:00+00:00
- Candidate: `ar1` model `-` input `log_price` context 512 horizon 1 bar(s)
- Walk-forward: 8 forward-chained folds, purge = horizon, embargo 24 bars, 16998 out-of-sample decision points
- Costs (per side bps): commission 5.0, half-spread 0.5, slippage 2.0; round trip 15.0 bps (1x), 30.0 bps (2x)
- Mean |tradable 1-bar return|: 31.5 bps
- **Break-even hit rate: 0.7378 (1x), 0.9757 (2x)**
- **Configuration variants in ledger (N for adjustment): 2**; this run's adjusted alpha = 0.05/2 = 0.02500
- Ledger-wide survivors: Holm 1, BH 1 of 2 variants with p-values

## Test A: directional edge (tradable open-to-open return)

| forecaster | n | hit rate | 95% CI | adj. lower bound | p (one-sided) | IC (Spearman) | IC 95% CI | trade frac | net/bar 1x (bps) | Sharpe 1x | net/bar 2x (bps) | Sharpe 2x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ar1 (candidate)** | 16998 | 0.5477 | [0.5400, 0.5550] | 0.5400 | 0.0000 | 0.1351 | [0.1203, 0.1492] | 1.00 | -10.42 | -23.89 | -25.42 | -58.28 |
| zero | 0 | nan | [nan, nan] | nan | nan | nan | [nan, nan] | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| last_sign | 16998 | 0.5504 | [0.5428, 0.5577] | 0.5428 | 0.0000 | 0.1035 | [0.0901, 0.1176] | 1.00 | -10.28 | -23.58 | -25.28 | -57.98 |
| ewma | 0 | nan | [nan, nan] | nan | nan | nan | [nan, nan] | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| garch | 0 | nan | [nan, nan] | nan | nan | nan | [nan, nan] | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Best constant-sign rate (always long or always short): 0.5083. Break-even: 0.7378 (1x) / 0.9757 (2x).

Same statistics on the forecast target (close-to-close), for reference only; you cannot trade this:

| forecaster | hit rate cc | 95% CI | IC cc |
|---|---|---|---|
| **ar1 (candidate)** | 0.5448 | [0.5370, 0.5522] | 0.1351 |
| zero | nan | [nan, nan] | nan |
| last_sign | 0.5480 | [0.5404, 0.5554] | 0.1039 |
| ewma | nan | [nan, nan] | nan |
| garch | nan | [nan, nan] | nan |

### Per-fold candidate hit rate (tradable)

| fold | n | hit rate | mean net/bar 1x (bps) |
|---|---|---|---|
| 0 | 2125 | 0.5384 | -11.22 |
| 1 | 2125 | 0.5642 | -9.45 |
| 2 | 2125 | 0.5492 | -10.32 |
| 3 | 2125 | 0.5431 | -10.06 |
| 4 | 2125 | 0.5501 | -10.22 |
| 5 | 2125 | 0.5473 | -11.05 |
| 6 | 2124 | 0.5476 | -10.07 |
| 7 | 2124 | 0.5414 | -10.94 |

## Test B: calibration (forecast target, close-to-close)

| forecaster | 20% cov | 40% cov | 60% cov | 80% cov | mean abs cov err | pinball (mean, 1e-4) | CRPS proxy (1e-4) |
|---|---|---|---|---|---|---|---|
| **ar1 (candidate)** | 0.226 | 0.444 | 0.646 | 0.826 | 0.0358 | 12.1455 | 24.2910 |
| zero | 0.225 | 0.447 | 0.649 | 0.825 | 0.0364 | 12.2688 | 24.5376 |
| last_sign | 0.164 | 0.339 | 0.522 | 0.735 | 0.0601 | 14.9795 | 29.9590 |
| ewma | 0.198 | 0.394 | 0.591 | 0.789 | 0.0069 | 12.0856 | 24.1712 |
| garch | 0.200 | 0.400 | 0.601 | 0.799 | 0.0007 | 12.0692 | 24.1384 |

Per-quantile empirical coverage P(y <= q_level):

| forecaster | q0.1 | q0.2 | q0.3 | q0.4 | q0.5 | q0.6 | q0.7 | q0.8 | q0.9 |
|---|---|---|---|---|---|---|---|---|---|
| **ar1 (candidate)** | 0.087 | 0.175 | 0.272 | 0.383 | 0.496 | 0.609 | 0.717 | 0.821 | 0.913 |
| zero | 0.086 | 0.171 | 0.270 | 0.380 | 0.493 | 0.605 | 0.717 | 0.820 | 0.911 |
| last_sign | 0.131 | 0.239 | 0.331 | 0.420 | 0.501 | 0.583 | 0.670 | 0.761 | 0.866 |
| ewma | 0.102 | 0.200 | 0.297 | 0.393 | 0.493 | 0.591 | 0.691 | 0.792 | 0.891 |
| garch | 0.098 | 0.195 | 0.295 | 0.392 | 0.493 | 0.592 | 0.694 | 0.796 | 0.897 |

![reliability](reliability_synthetic_ar1_phi015.png)

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
