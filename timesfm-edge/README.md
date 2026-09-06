# TimesFM edge test harness

Does a time-series foundation model (TimesFM 2.5 / 3.0) have an exploitable
directional edge on a financial instrument? This repo is built to answer that
question adversarially. A clean negative is a successful outcome.

Phase 1 (the gate) is complete and validated. Phase 2 (decision, risk,
execution) is **deliberately not built**: `decision/`, `risk/` and `execution/`
contain only a note saying so, and `analysis/phase1.py` imports nothing from them.

> **Read [`SETUP.md`](SETUP.md) before running anything.** The first pass at this
> project needed a 73.8% hit rate to break even, which no model clears. That hurdle
> came from the setup, not from markets: it is set by `k = round-trip cost / per-bar
> volatility`, which ranges over a factor of forty across ordinary retail-accessible
> instruments. Check `python -m tfm_edge.analysis.feasibility` before spending hours
> on inference, because arithmetic can rule a setup out in a second.

![feasibility](reports/feasibility.png)

## Assumed parameters

The build prompt left the parameters as placeholders, so the harness ships with
these defaults. Every one is a config value; change them in `config/*.yaml`.

| parameter | default | where |
|---|---|---|
| instrument | BTCUSDT USDS-M perpetual (Binance) | `data.symbol`, `data.market` |
| data source | Binance public klines, no key, parquet-cached | `data.source` (`binance`, `csv`, `synthetic`) |
| bar | 1 hour | `data.bar` |
| horizon | 1 bar | `forecast.horizon` |
| history | 4 years | `data.years` |
| environment | Python 3.11, CPU | `forecast.device` |
| model | `google/timesfm-2.5-200m-pytorch` (Apache-2.0 weights) | `forecast.model_id` |
| costs, per side | 5 bps taker + 0.5 bps half-spread + 2 bps slippage = 15 bps round trip | `costs.*` |

Capital at risk is not needed until Phase 2 and is not assumed anywhere.

**Licence warning.** TimesFM 3.0 pretrained weights are distributed under a
non-commercial, non-production licence. Running them through Phase 1 is
research; trading money on them is not permitted. TimesFM 2.5 weights are
Apache-2.0. The default config uses 2.5 for that reason.

## One command

```bash
pip install -r requirements.txt
./run_phase1.sh                                   # tests, feasibility, self-tests, setup comparison
./run_phase1.sh config/btc_1h_timesfm30.yaml      # one single-instrument config
./run_phase1.sh --xs config/xs_crypto_1d_timesfm25.yaml   # one cross-sectional config
```

Standalone tools:

```bash
python -m tfm_edge.analysis.feasibility --ic 0.03   # what does each setup need from the model?
python -m tfm_edge.analysis.compare_setups          # same planted edge, five setups, five verdicts
```

Each run writes `reports/phase1_<name>.md` (the findings), `.json` (every
number) and `reliability_<name>.png`, and appends to the experiment ledger.

CLI overrides such as `--horizon 4` or `--input-mode log_return` are allowed
and each one **counts as a new configuration variant in the ledger**.

## Hard constraints and where they are enforced

1. **Returns, never price levels.** `features/samples.py` defines the only
   targets: `y_cc` (close-to-close H-bar log return, the forecast target) and
   `y_oo` (open-to-open, the tradable return). TimesFM may be *fed* log prices,
   but its output is differenced against the last close before any metric sees it.
2. **No look-ahead.** Bars carry `knowable_at = close_time`. A decision at bar t
   uses `context[..t]`, executes at `open_time[t+1]`, and both targets start
   after that. `tests/test_no_lookahead.py` proves the harness catches a peek.
   Walk-forward is forward-chained with purge = horizon and a pre-test embargo
   (`analysis/walkforward.py`), asserted on every fold.
3. **Deterministic decision layer.** Not built yet (gated). The contract is in
   `decision/__init__.py`.
4. **Costs never optional.** Every Test A row reports net P&L at 1x and 2x costs,
   and the gate uses a break-even hit rate derived from the cost model.

## Two setups worth running, and one that is not

Full derivation in [`SETUP.md`](SETUP.md). Summary of what each lever is worth:

| lever | worth | why |
|---|---|---|
| cheaper instrument / longer bar | up to 40x | cost is per round trip, volatility grows with sqrt(holding period) |
| cross-section + residualisation | 3-4x | removes the unpredictable market factor from both input and target, and adds breadth |
| turnover accounting | 2x | the original harness charged a full round trip every bar instead of on position change |
| selection threshold | up to 3x | concentrates the edge, though not the move size |
| score smoothing | 2-4x | turnover, not forecast quality, is what kills a daily cross-sectional book |

| config | what it is | break-even hit rate |
|---|---|---|
| `config/xs_crypto_1d_timesfm25.yaml` | cross-sectional, market-neutral, daily, residualised | ~0.53 on relative moves, plus breadth |
| `config/futures_1d_timesfm25.yaml` | MES daily, the cheapest single instrument available | 0.508 |
| `config/btc_1h_timesfm25.yaml` | where this project started | **0.738** |

## Phase 1

**Test A, directional edge.** Out-of-sample hit rate of `sign(forecast)` vs
`sign(y_oo)` with a circular block-bootstrap CI (block length max(H, n^(1/3)),
because overlapping labels and vol clustering make hits serially dependent).
Baselines: always-zero (compared via the best constant-sign rate), last-sign,
AR(1) on returns. Spearman IC with a bootstrap CI. Bonferroni-adjusted lower
bound using N = number of distinct variants in the ledger.

**Test B, calibration.** Empirical coverage of the 20/40/60/80% central
intervals and of each of the nine quantiles, pinball loss and a CRPS proxy,
against GARCH(1,1)-t and EWMA(0.94) baselines. Reliability diagram saved as PNG.

**Test C, the strategy.** Hit rate is a weak objective and cannot see the threshold
sweep, which is the largest multiple-testing surface in the project. So the candidate is
also evaluated as the strategy you would actually run: turnover-aware (cost charged on
position change, not on holding), selective (stand aside below a threshold), and sized.
The winning cell is scored with a **Deflated Sharpe Ratio** that counts every cell of the
sweep plus every ledger variant as a trial, and cells are selected on their **2x-cost**
Sharpe, because ranking on the headline systematically picks the most cost-fragile
configuration. Both verdicts are reported and both must be read.

**Multiple testing.** `analysis/ledger.py` registers each variant *before* it is
evaluated and is append-only across runs. `reports/experiment_ledger.json` is
the count. Deleting it resets N and is p-hacking; the synthetic ledger is
committed as the record of what was run here.

### Gate criteria (fixed in `analysis/gate.py` before any real result exists)

- **PROCEED**: on the tradable return, the Bonferroni-adjusted lower confidence
  bound of the candidate hit rate exceeds the 1x break-even hit rate, AND the
  candidate's hit rate beats last-sign, AR(1) and the best constant sign.
  Labelled `PROCEED_FRAGILE` if it fails the same test at 2x costs.
- **VOL_MODEL_ONLY**: Test A fails; Test B passes (mean absolute coverage error
  over the four intervals at most 5 points AND pinball loss below both GARCH and
  EWMA). You have a volatility model, not a signal.
- **STOP**: both fail.

Break-even hit rate: `0.5 + c / (2 E|r|)` where c is the round-trip cost and
E|r| the mean absolute tradable move over the horizon, measured out of sample.
The formula assumes |move| is independent of correctness, which is optimistic.

## Harness self-tests (must pass before reading any real number)

| series | expectation | result |
|---|---|---|
| martingale + GARCH vol (`config/synthetic_random_walk.yaml`) | no edge found, STOP | hit rate 0.502, CI [0.495, 0.510], STOP |
| AR(1) phi=0.15 (`config/synthetic_ar1.yaml`), theory 0.548 | edge found, not tradable at 15 bps | hit rate 0.548, CI [0.540, 0.555], break-even 0.738, STOP |
| panel, no edge anywhere (`config/xs_synthetic_null.yaml`) | no edge found, STOP | cross-sectional IC 0.003, DSR 0.000, STOP |
| panel, idiosyncratic AR(1) phi=0.06 (`config/xs_synthetic_edge.yaml`) | edge found and tradable | IC 0.061, Sharpe 3.87 (1.83 at 2x costs), DSR 0.974, PROCEED |

See `FINDINGS.md` for the full read.

## Layout

```
config/               run configs (synthetic self-tests, BTC 1h on TimesFM 2.5 and 3.0)
tfm_edge/config.py    dataclasses; variant_hash() defines what counts as one hypothesis
tfm_edge/data/        bars schema + validation, Binance loader, CSV loader, synthetic
                      generators, multi-asset panels
tfm_edge/features/    point-in-time samples and targets, cross-sectional construction
tfm_edge/model/       Forecaster protocol, baselines, TimesFM wrapper, content-addressed cache
tfm_edge/analysis/    feasibility arithmetic, walk-forward, metrics, deflated Sharpe,
                      turnover-aware portfolio, ledger, gates, reports, entry points
                      (phase1 = single instrument, panel_run = cross-sectional,
                       compare_setups = same edge across setups)
tfm_edge/decision/    gated (empty)
tfm_edge/risk/        gated (empty)
tfm_edge/execution/   gated (empty)
tests/                46 tests: leak detection, purge/embargo, bootstrap coverage, calibration,
                      gate logic, ledger persistence, feasibility identities, turnover
                      accounting, deflated-Sharpe behaviour, cross-sectional leak detection,
                      end-to-end on synthetic data, TimesFM plumbing
reports/              generated reports and the experiment ledger
```

## Running on your own data

- Binance: set `data.source: binance`; the first run downloads and caches.
- CSV: `data.source: csv`, `data.csv_path: path`, columns
  `open_time,open,high,low,close,volume` with `open_time` = bar start.
  Bars must be gapless; the loader refuses gaps rather than forward-filling.
- TimesFM inference on CPU: about 0.3 s per 512-bar context for 2.5-200M in
  batches of 32. `walkforward.max_test_points` caps calls per fold; forecasts
  are cached by content so re-runs are free.
