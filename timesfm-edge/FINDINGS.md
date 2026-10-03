# Findings

> **Update.** The original setup could not have passed. It needed a 73.8% hit rate to
> break even, and that number came from the configuration, not from the model or the
> market. [`SETUP.md`](SETUP.md) works out why, and what to run instead. This document
> records what the first pass found; read both.

Status: **Phase 1 harness built and validated on synthetic data. No real-data result
yet.** The container this was built in cannot reach Binance, Yahoo or HuggingFace,
so the gate has not been run on the real instrument. Everything below is what
the harness does when the answer is known in advance, which is the only way to
trust what it says when the answer is not.

## What was run

| run | variant hash | candidate | n OOS | hit rate (tradable) | 95% CI | adj. lower bound | break-even 1x / 2x | IC | verdict |
|---|---|---|---|---|---|---|---|---|---|
| synthetic random walk | `f011…` | AR(1) | 16,998 | 0.5024 | [0.4952, 0.5099] | 0.4964 | 0.7487 / 0.9975 | -0.007 | STOP |
| synthetic AR(1), phi = 0.15 | `fde2…` | AR(1) | 16,998 | 0.5477 | [0.5400, 0.5550] | 0.5400 | 0.7378 / 0.9757 | 0.135 | STOP |

Configuration variants in the synthetic ledger: **2**. Real-data ledger: **0**.
(Full tables, per-fold rows and Test B numbers are in `reports/phase1_*.md`.)

Baselines on the AR(1) series: last-sign 0.5504, best constant sign 0.5083.
Baselines on the random walk: last-sign 0.4952, best constant sign 0.5046.

Test B on the random walk (GARCH-generated volatility): GARCH(1,1)-t mean absolute
coverage error 0.004, EWMA 0.011, constant-sigma AR(1) 0.028. GARCH pinball
11.51e-4 vs AR(1) 11.65e-4. The volatility baselines are working and are hard to beat
on a series whose vol actually is GARCH.

## Honest read

1. **The harness is not blind.** It recovers the planted AR(1) edge at 0.548 against a
   theoretical 0.5 + asin(0.15)/pi = 0.548, with a CI that excludes 0.5 and a Spearman
   IC of 0.135.
2. **The harness is not leaky.** On a martingale it reports 0.502 with a CI containing
   0.5, and the peek test in `tests/test_no_lookahead.py` shows a one-bar leak would
   score above 0.99.
3. **The bar is very high, and that is the real finding so far.** At 15 bps round trip
   and a mean absolute hourly move of about 31 bps, the break-even hit rate is 0.74.
   Even a *known, strong* one-bar autocorrelation of 0.15, which is far larger than
   anything documented in liquid crypto at hourly frequency, loses 10 bps per bar
   after costs. For TimesFM to pass, it would need to be roughly five times more
   directionally accurate than an AR(1) on a series designed for AR(1). Expect STOP
   or VOL_MODEL_ONLY on real BTC 1h data. If you want a passing gate to be possible at
   all, the levers are lower costs (maker fills, a cheaper venue), a longer horizon
   (E|r| grows roughly with sqrt(H), costs do not), or a less efficient instrument.
4. **Last-sign is a serious baseline.** On the AR(1) series it ties the fitted AR(1)
   (0.550 vs 0.548, within the CI). Any TimesFM result must beat it, and a level-input
   foundation model that extrapolates the recent slope is likely to *be* a smoothed
   last-sign predictor. Run both input modes and compare to last-sign before believing
   a number.

## What would make a positive real-data result spurious

Written before the real run, so it cannot be tuned to the result:

- A timestamp convention error in the feed (close-time stored as open-time) would be
  a one-bar leak. The unit tests cannot see this; check the feed against a second
  source by hand.
- The ledger only counts what this harness ran. Variants tried in a notebook are
  uncounted and N is understated.
- Eight folds over four years is one path through one regime sequence. A pass
  concentrated in one or two folds is a regime, not an edge; the per-fold table is
  there to show it.
- Costs are constant in the model and are not constant in reality. Spread and
  slippage widen in exactly the bars with the largest |returns|, which are the bars
  that dominate the hit-rate P&L.
- The break-even formula assumes |move| is independent of correctness. Foundation
  models are slow on jumps; if errors concentrate on large moves the true break-even
  is higher than printed.
- Perpetual funding is ignored. Over a multi-hour hold it is a cost or an income of
  up to a few bps and it is not in the numbers.

## Assumptions most likely to be wrong

1. Fills at the next open at the assumed 7.5 bps per side, no partial fills, no funding.
2. |realised move| independent of forecast correctness (break-even formula).
3. Block-bootstrap block length of n^(1/3) bars (26 here) spans the serial dependence.
   Hourly crypto vol clusters can persist for days; a longer block widens the CI.
4. TimesFM's internal normalisation and (3.0) linear detrending behave on log-price
   inputs. If they do not, the log_price variant is mostly extrapolating slope.
5. Multi-step quantile spreads in log_return mode combine as if steps were independent.
6. GARCH is fitted once per fold and filtered forward, not refitted daily, so the
   calibration baseline is slightly weaker than a practitioner's.
7. Synthetic series are Gaussian-GARCH. Real returns have jumps and fat tails.
8. Binance perpetual klines represent a tradable price. Cross-venue arbitrage makes
   the printed close stale by the next open.

## The setup was the binding constraint, not the model

Point 3 above turned out to be the whole story, and it is fixable. Working through the
arithmetic (full derivation in [`SETUP.md`](SETUP.md)):

- The break-even hit rate reduces to `0.5 + 0.627k` where `k` is round-trip cost divided
  by per-bar volatility. `k` ranges from 0.379 (hourly BTC perps at taker fees) to 0.009
  (index futures on daily bars) across ordinary retail-accessible setups. The original
  configuration sat at the worst end of a forty-fold range.
- The harness itself was charging a full round trip on every bar rather than on position
  change, overstating costs by at least 2x. That was a bug in the pessimistic direction.
- A dollar-neutral cross-sectional book removes the market factor, which is the least
  predictable and most volatile part of the return, from both the model input and the
  target. On the synthetic panel that lifts IC from 0.070 to 0.101 while cutting target
  volatility from 364 to 300 bps.
- Breadth is the only lever that improves statistical power as well as return. It takes
  the track record needed to distinguish a result from luck from 9.7 years to 4.9.

Demonstrated end to end: one synthetic panel, one small planted idiosyncratic edge
(phi = 0.06), five ways of trading it.

| setup | IC | Sharpe | Sharpe 2x | DSR | verdict |
|---|---|---|---|---|---|
| 1 asset, daily, crypto taker | 0.028 | 0.85 | 0.55 | 0.630 | `STOP` |
| 60 assets, no residualisation | 0.050 | 3.65 | 1.74 | 0.860 | `STOP` |
| 60 assets, beta residualisation | 0.061 | 3.87 | 1.83 | 0.972 | `PROCEED` |
| 60 assets, maker fees | 0.061 | 7.13 | 6.10 | 1.000 | `PROCEED` |
| 60 assets, equity fees | 0.061 | 7.39 | 6.61 | 1.000 | `PROCEED` |

Nothing about the signal changes between rows. These Sharpe levels are far above
anything real data will produce; the ratios between rows are the finding.

**This does not mean an edge exists.** It means the experiment became worth running.
The hurdle went from impossible to plausible; whether TimesFM clears it is still open,
and the honest prior for a zero-shot foundation model on liquid instruments is an IC
near zero.

## What to do next

1. On a machine with network access: `./run_phase1.sh`. It runs the tests, the
   feasibility survey, all four self-tests, and the setup comparison.
2. Then run the two configurations worth running:
   `./run_phase1.sh --xs config/xs_crypto_1d_timesfm25.yaml` and, if you have futures
   bars, `./run_phase1.sh config/futures_1d_timesfm25.yaml`. Do not start with
   `config/btc_1h_timesfm25.yaml`; it is kept as the record of where this began.
3. Read the strategy verdict and the hit-rate verdict together, then the per-fold row,
   then the last-sign baseline. If last-sign wins you have rediscovered momentum.
4. If the verdict is VOL_MODEL_ONLY: that is a usable result. A calibrated distribution
   of the next period's return is worth money for position sizing (volatility-managed
   portfolios are a documented source of Sharpe improvement), for setting bracket widths
   that stay stable across regimes, and for timing variance-premium trades. It is not a
   trading signal and Phase 2 as specified should not be built.
5. If the verdict is STOP on a setup whose feasibility row said it was reachable: stop.
   Do not tune. The ledger records every variant you try anyway, and the deflated Sharpe
   uses that count.

## New risks introduced by the better setup

The levers are arithmetic and they are sound, but the risks moved rather than vanished.
Fuller list in `SETUP.md` section 6.

1. **Maker fills are not backtestable from OHLCV bars.** No adverse selection, no fill
   failure, and the unfilled bars are exactly the favourable ones. Treat every maker
   number here as an upper bound.
2. **Effective breadth is a guess.** Twelve independent bets from sixty crypto perps is
   plausible, not measured. Measure it from the residual correlation matrix.
3. **Panel survivorship.** A universe picked today by liquidity is a list of survivors.
   It must be reconstructed as it stood at each point in time.
4. **Cross-sectional books carry borrow, funding and 60 spreads** that the
   single-instrument case does not.
5. **Costs are state-dependent and modelled as constant**, and they widen precisely in
   the volatile bars a selective strategy most wants to trade.
