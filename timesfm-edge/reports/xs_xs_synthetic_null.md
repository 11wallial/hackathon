# Cross-sectional Phase 1: xs_synthetic_null

Generated 2026-09-06T08:55:19.169929+00:00. Variant `2a97c3ae9b68`.

**Verdict: `STOP`**

- deflated Sharpe 0.0000 vs threshold 0.95, deflated against 5 trials: fails
- annualised Sharpe at 2x costs -6.715: negative
- Sharpe -3.038 vs last_sign -2.464: does not beat
- positive in 0/6 folds: concentrated
- 5.5 years of data vs inf needed to detect Sharpe -3.04: underpowered

## Setup

- Panel: 60 assets x 2600 1d bars, 1998 out-of-sample bars (5.5 years)
- Residualisation: `beta`; dollar-neutral, gross 1.0
- Round-trip cost 15.0 bps, charged on realised turnover
- Ledger variants: 1

## Result

| forecaster | cross-sectional IC | best slice | Sharpe | Sharpe 2x costs | turnover/bar | net bps/bar | DSR |
|---|---|---|---|---|---|---|---|
| ar1 (candidate) | +0.0030 | 0.5 | -3.038 | -6.715 | 1.00 | -6.21 | 0.0000 |
| last_sign | -0.0044 | 0.1 | -2.464 | -4.429 | 1.18 | -11.04 | 0.0000 |

Per-fold Sharpe of the candidate: [-2.57, -4.89, -2.38, -2.94, -3.28, -2.28]

Track record needed to detect Sharpe -3.04: inf years; available: 5.5.

## Slice-width sweep (every cell counts as a trial in the deflation)

| slice | Sharpe | Sharpe 2x | net bps/bar | turnover | names held |
|---|---|---|---|---|---|
| 0.1 | -3.071 | -6.046 | -13.97 | 1.80 | 12 |
| 0.2 | -3.583 | -7.294 | -11.61 | 1.60 | 24 |
| 0.3 | -3.344 | -7.290 | -8.93 | 1.41 | 36 |
| 0.5 | -3.038 | -6.715 | -6.21 | 1.00 | 60 |
