"""Cross-sectional Phase 1: does the model rank a universe better than chance?

    python -m tfm_edge.analysis.panel_run --config config/xs_synthetic_edge.yaml

Same discipline as the single-instrument gate (purged, embargoed, forward-chained folds;
targets that start after execution; an append-only ledger) applied to a dollar-neutral
book, which is the configuration where the cost arithmetic is survivable.

Per fold:
  1. Estimate betas on the training block only.
  2. Residualise the log-price series with those betas, so the model sees each asset's
     path relative to the market instead of the market itself.
  3. Forecast every asset at every test bar from its own residual context window.
  4. Z-score the forecasts ACROSS the cross-section of that bar. Only that bar's
     forecasts are used, so this is point-in-time.
  5. Long the top slice, short the bottom, equal weight, dollar neutral.
  6. Charge cost on realised turnover, sweep the slice width, score with a Deflated
     Sharpe that counts every cell of the sweep as a trial.
"""
from __future__ import annotations

import argparse
import dataclasses
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..config import RunConfig, load_config
from ..data.bars import bar_timedelta
from ..data.panel import Panel, generate_panel, panel_from_frames
from ..features.cross_section import (
    book_pnl, build_book, build_panel_samples, estimate_betas, neutralise_targets,
    residual_log_close,
)
from ..model.baselines import BASELINES
from ..model.factory import make_forecaster
from .deflated_sharpe import deflated_sharpe, sharpe
from .feasibility import min_track_record_years
from .gate import evaluate_strategy_gate
from .ledger import Ledger
from .report import save_json
from .walkforward import make_folds_from_index


def bars_per_year(bar: str) -> float:
    return float(np.timedelta64(365, "D") / bar_timedelta(bar).to_timedelta64())


def load_panel(cfg: RunConfig) -> Panel:
    xs, d = cfg.cross_section, cfg.data
    if d.source == "synthetic":
        return generate_panel(d.synthetic_n, xs.n_assets, bar=d.bar, seed=d.synthetic_seed,
                              phi_idio=xs.synthetic_phi_idio)
    if d.source == "binance":
        from ..data.binance import fetch_klines
        if not xs.symbols:
            raise ValueError("cross_section.symbols required for a Binance panel")
        frames = {s: fetch_klines(s, d.bar, d.years, market=d.market, cache_dir=d.cache_dir)
                  for s in xs.symbols}
        return panel_from_frames(frames, d.bar)
    raise ValueError(f"panel mode does not support source {d.source}")


def forecast_panel(name, fc, panel: Panel, samples, folds, cfg: RunConfig, log) -> np.ndarray:
    """(n_times, n_assets) raw forecasts, filled fold by fold. NaN where not forecast."""
    H, C = cfg.forecast.horizon, cfg.forecast.context_len
    pred = np.full(samples.y_cc.shape, np.nan)
    rets = panel.returns()
    for fold in folds:
        t0 = time.time()
        betas = estimate_betas(rets, fold.train_return_end)
        series = residual_log_close(panel, betas, cfg.cross_section.residualise)
        # order="F" keeps each asset's history contiguous. Row-major ravel would put
        # different assets at the same bar next to each other, and an AR(1) fitted on
        # that measures cross-sectional correlation, not autocorrelation.
        train = np.diff(series[:fold.train_return_end], axis=0).ravel(order="F")
        fc.fit(train[np.isfinite(train)])
        times = samples.t[fold.test_sample_idx]
        windows, slots = [], []
        for row, t in zip(fold.test_sample_idx, times):
            for a in range(panel.n_assets):
                windows.append(series[max(0, t - C + 1):t + 1, a])
                slots.append((row, a))
        d = fc.predict(windows, H).sorted()
        for (row, a), p in zip(slots, d.point):
            pred[row, a] = p
        log(f"  [{name}] fold {fold.k}: {len(windows)} forecasts ({len(times)} bars x {panel.n_assets} assets) in {time.time()-t0:.1f}s")
    return pred


def cross_sectional_scores(pred: np.ndarray) -> np.ndarray:
    """Z-score within each bar's cross-section. Uses only that bar, so point-in-time."""
    out = np.full_like(pred, np.nan)
    usable = np.isfinite(pred).sum(axis=1) >= 2      # bars outside every fold are all-NaN
    if not usable.any():
        return out
    p = pred[usable]
    mu = np.nanmean(p, axis=1, keepdims=True)
    sd = np.nanstd(p, axis=1, keepdims=True)
    out[usable] = (p - mu) / np.where(sd > 0, sd, 1.0)
    return out


def smooth_scores(scores: np.ndarray, halflife: float) -> np.ndarray:
    """Backward-looking EWMA of each asset's score.

    Turnover, not forecast quality, is what kills a daily cross-sectional book: a full
    rebalance of a 60-name panel at 7.5 bps a side costs more per year than most real
    signals earn. Smoothing trades a little signal freshness for a large cut in
    turnover, and only uses past scores."""
    if halflife <= 0:
        return scores
    lam = 0.5 ** (1.0 / halflife)
    out = np.empty_like(scores)
    acc = np.zeros(scores.shape[1])
    wsum = 0.0
    for i in range(scores.shape[0]):
        row = np.nan_to_num(scores[i], nan=0.0)
        acc = lam * acc + row
        wsum = lam * wsum + 1.0
        out[i] = acc / wsum
    return out


def hold_between_rebalances(w: np.ndarray, every: int) -> np.ndarray:
    """Recompute the book only every `every` bars and hold in between."""
    if every <= 1:
        return w
    out = w.copy()
    for i in range(len(w)):
        if i % every:
            out[i] = out[i - 1]
    return out


def evaluate_book(scores, y, cfg: RunConfig, bpy: float, fold_of, n_prior_trials: int):
    """Sweep the slice width, charge turnover, deflate the winner against the sweep."""
    rt = cfg.costs.round_trip_frac()
    rows, series, sharpes = [], [], []
    for tf in cfg.strategy.top_fractions:
        for hl in cfg.strategy.smoothing_halflives:
            for ev in cfg.strategy.rebalance_intervals:
                sm = smooth_scores(scores, hl)
                w = hold_between_rebalances(build_book(sm, tf, cfg.cross_section.gross), ev)
                net, stats = book_pnl(w, y, rt)
                net2, _ = book_pnl(w, y, 2 * rt)
                rows.append({"top_fraction": tf, "smoothing_halflife": hl, "rebalance_every": ev, **stats,
                             "sharpe_annual": float(sharpe(net) * np.sqrt(bpy)),
                             "sharpe_annual_2x": float(sharpe(net2) * np.sqrt(bpy))})
                series.append(net)
                sharpes.append(sharpe(net))
    # Select on the 2x-cost Sharpe, not the headline. Ranking cells by their 1x Sharpe
    # systematically picks the highest-turnover cell, whose apparent edge is the most
    # dependent on the cost assumption being right. Choosing on 2x and reporting both
    # makes the selection robust by construction rather than by hope.
    best = int(np.argmax([r["sharpe_annual_2x"] if r["turnover_per_bar"] > 1e-9 else -np.inf for r in rows]))
    n_trials = len(rows) + n_prior_trials
    d = deflated_sharpe(series[best], n_trials, np.array(sharpes), bpy, cfg.strategy.dsr_alpha)
    fold_sharpes = []
    for k in sorted(set(fold_of)):
        m = fold_of == k
        fold_sharpes.append(float(sharpe(series[best][m]) * np.sqrt(bpy)) if m.sum() > 5 else 0.0)
    return {
        "grid": rows, "best": rows[best], "dsr": dataclasses.asdict(d),
        "net_series_mean_bps": float(1e4 * series[best].mean()),
    }, series[best], fold_sharpes, rows[best]["sharpe_annual_2x"]


def run(cfg: RunConfig, log=print) -> dict:
    t_start = time.time()
    log(f"== Cross-sectional Phase 1: {cfg.name} (variant {cfg.variant_hash()})")
    panel = load_panel(cfg)
    log(f"  panel: {panel.n_bars} bars x {panel.n_assets} assets, {cfg.data.bar}, residualise={cfg.cross_section.residualise}")
    samples = build_panel_samples(panel, cfg.forecast.horizon, cfg.forecast.context_len)
    folds = make_folds_from_index(samples.t, samples.horizon, cfg.walkforward)
    for f in folds:
        log(f"  fold {f.k}: train bars [0,{f.train_return_end}) test {len(f.test_sample_idx)} bars")

    ledger = Ledger(cfg.stats.ledger_path)
    n_prior = ledger.record(cfg.variant_hash(), cfg.variant_key())
    log(f"  ledger: variant #{n_prior}")

    bpy = bars_per_year(cfg.data.bar)
    rets = panel.returns()
    rows = np.concatenate([f.test_sample_idx for f in folds])
    fold_of = np.concatenate([np.full(len(f.test_sample_idx), f.k) for f in folds])

    # neutralise the realised target with each fold's own betas, so nothing forward-looking
    y = np.full(samples.y_oo.shape, np.nan)
    for f in folds:
        b = estimate_betas(rets, f.train_return_end)
        y[f.test_sample_idx] = neutralise_targets(samples.y_oo, b, cfg.cross_section.residualise)[f.test_sample_idx]

    results, series_by = {}, {}
    cand_name = cfg.forecast.forecaster
    for name, fc in [(cand_name, make_forecaster(cfg.forecast))] + [(n, c()) for n, c in BASELINES.items() if n != cand_name and n not in ("zero", "ewma", "garch")]:
        pred = forecast_panel(name, fc, panel, samples, folds, cfg, log)
        scores = cross_sectional_scores(pred)[rows]
        sweep, net, fold_sharpes, s2x = evaluate_book(scores, y[rows], cfg, bpy, fold_of, n_prior)
        ic = float(np.corrcoef(scores[np.isfinite(scores) & np.isfinite(y[rows])].ravel(),
                               y[rows][np.isfinite(scores) & np.isfinite(y[rows])].ravel())[0, 1])
        years = len(rows) / bpy
        results[name] = {
            "sweep": sweep, "fold_sharpes": fold_sharpes, "sharpe_2x": s2x,
            "cross_sectional_ic": ic, "years_of_data": years,
            "years_to_prove": min_track_record_years(sweep["best"]["sharpe_annual"]),
        }
        series_by[name] = net
        log(f"  [{name}] IC {ic:+.4f}  best Sharpe {sweep['best']['sharpe_annual']:.3f} "
            f"(2x costs {s2x:.3f})  slice {sweep['best']['top_fraction']} smooth {sweep['best']['smoothing_halflife']} "
            f"rebal {sweep['best']['rebalance_every']}  turnover {sweep['best']['turnover_per_bar']:.2f}  DSR {sweep['dsr']['deflated_sharpe']:.4f}")

    candidate = results[cand_name]
    baselines = {k: v for k, v in results.items() if k != cand_name}
    verdict = evaluate_strategy_gate(candidate, baselines, cfg.strategy.dsr_alpha)
    ledger.record(cfg.variant_hash(), cfg.variant_key(), {
        "sharpe": candidate["sweep"]["best"]["sharpe_annual"],
        "p_value": 1.0 - candidate["sweep"]["dsr"]["deflated_sharpe"],
        "ic": candidate["cross_sectional_ic"], "verdict": verdict.verdict,
    })

    res = {
        "name": cfg.name, "mode": "cross_sectional",
        "generated_at": datetime.now(timezone.utc).isoformat(), "variant_hash": cfg.variant_hash(),
        "config": cfg.to_dict(), "n_assets": panel.n_assets, "n_bars": panel.n_bars,
        "n_test_bars": int(len(rows)), "bars_per_year": bpy,
        "round_trip_bps": cfg.costs.round_trip_bps(), "ledger_count": n_prior,
        "candidate": candidate, "baselines": baselines,
        "gate": dataclasses.asdict(verdict), "runtime_s": time.time() - t_start,
    }
    out = Path(cfg.report_dir)
    out.mkdir(parents=True, exist_ok=True)
    save_json(res, out / f"xs_{cfg.name}.json")
    write_panel_report(res, out / f"xs_{cfg.name}.md")
    log(f"== verdict: {verdict.verdict}")
    for r in verdict.reasons:
        log("   - " + r)
    log(f"== report: {out / f'xs_{cfg.name}.md'} ({res['runtime_s']:.0f}s)")
    return res


def write_panel_report(res: dict, path: Path) -> None:
    c, g = res["candidate"], res["gate"]
    L = [f"# Cross-sectional Phase 1: {res['name']}\n",
         f"Generated {res['generated_at']}. Variant `{res['variant_hash']}`.\n",
         f"**Verdict: `{g['verdict']}`**\n"]
    L += [f"- {r}" for r in g["reasons"]]
    L += ["", "## Setup\n",
          f"- Panel: {res['n_assets']} assets x {res['n_bars']} {res['config']['data']['bar']} bars, "
          f"{res['n_test_bars']} out-of-sample bars ({c['years_of_data']:.1f} years)",
          f"- Residualisation: `{res['config']['cross_section']['residualise']}`; dollar-neutral, gross {res['config']['cross_section']['gross']}",
          f"- Round-trip cost {res['round_trip_bps']:.1f} bps, charged on realised turnover",
          f"- Ledger variants: {res['ledger_count']}", "",
          "## Result\n",
          "| forecaster | cross-sectional IC | best slice | Sharpe | Sharpe 2x costs | turnover/bar | net bps/bar | DSR |",
          "|---|---|---|---|---|---|---|---|"]
    for name, r in [(res["config"]["forecast"]["forecaster"] + " (candidate)", c)] + list(res["baselines"].items()):
        b, d = r["sweep"]["best"], r["sweep"]["dsr"]
        L.append(f"| {name} | {r['cross_sectional_ic']:+.4f} | {b['top_fraction']} | {b['sharpe_annual']:.3f} | "
                 f"{r['sharpe_2x']:.3f} | {b['turnover_per_bar']:.2f} | {b['mean_net_bps']:.2f} | {d['deflated_sharpe']:.4f} |")
    L += ["", f"Per-fold Sharpe of the candidate: {[round(x,2) for x in c['fold_sharpes']]}", "",
          f"Track record needed to detect Sharpe {c['sweep']['best']['sharpe_annual']:.2f}: "
          f"{c['years_to_prove']:.1f} years; available: {c['years_of_data']:.1f}.", "",
          "## Sweep (every cell counts as a trial in the deflation)\n",
          "| slice | smooth hl | rebal every | Sharpe | Sharpe 2x | net bps/bar | turnover | names held |",
          "|---|---|---|---|---|---|---|---|"]
    for r in sorted(c["sweep"]["grid"], key=lambda x: -x["sharpe_annual"]):
        L.append(f"| {r['top_fraction']} | {r['smoothing_halflife']} | {r['rebalance_every']} | "
                 f"{r['sharpe_annual']:.3f} | {r['sharpe_annual_2x']:.3f} | "
                 f"{r['mean_net_bps']:.2f} | {r['turnover_per_bar']:.2f} | {r['avg_names_held']:.0f} |")
    path.write_text("\n".join(L) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--forecaster")
    ap.add_argument("--residualise", choices=["none", "demean", "beta"])
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.forecaster:
        cfg = dataclasses.replace(cfg, forecast=dataclasses.replace(cfg.forecast, forecaster=a.forecaster),
                                  name=f"{cfg.name}_{a.forecaster}")
    if a.residualise:
        cfg = dataclasses.replace(cfg, cross_section=dataclasses.replace(cfg.cross_section, residualise=a.residualise),
                                  name=f"{cfg.name}_resid={a.residualise}")
    run(cfg)


if __name__ == "__main__":
    main()
