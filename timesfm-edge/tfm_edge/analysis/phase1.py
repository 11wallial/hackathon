"""Phase 1 entry point. One command reproduces Test A, Test B and the gate:

    python -m tfm_edge.analysis.phase1 --config config/btc_1h_timesfm25.yaml

Everything the gate needs is computed here; nothing from decision/, risk/ or
execution/ is imported (those stay empty until the gate passes).
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
from ..data.loader import load_bars
from ..features.samples import build_samples, context_window, log_returns
from ..model.baselines import BASELINES
from ..model.factory import make_forecaster
from . import metrics as M
from .feasibility import min_track_record_years, naive_break_even_hit_rate
from .gate import evaluate_gate, evaluate_strategy_gate
from .deflated_sharpe import sharpe as _sharpe
from .portfolio import expanding_standardise, sweep as strategy_sweep
from .ledger import Ledger
from .report import reliability_diagram, save_json, write_report
from .walkforward import assert_no_overlap, make_folds

ASSUMPTIONS = [
    "Execution at the next bar's open at the assumed cost; no partial fills, no funding payments (perpetuals pay funding every 8h, which is a further cost or income the model ignores).",
    "Costs are constant. Spread and slippage widen exactly when volatility spikes, which is also when |return| and therefore apparent 'edge' are largest.",
    "|realised move| is independent of forecast correctness (used in the break-even formula). Usually false; errors cluster on large moves.",
    "Bars from a single venue represent the price you could trade at. Cross-venue arbitrage bots make the printed close a stale number by the next open.",
    "The circular block bootstrap block length (n^(1/3), at least H) spans the serial dependence. Volatility clustering in hourly crypto can persist for days.",
    "The multiple-testing count only includes variants recorded in the ledger. Anything tried outside this harness is uncounted.",
    "TimesFM's normalisation and detrending (RevIN, linear detrending in 3.0) is well-behaved on log-price inputs; a level-input forecast that mostly extrapolates the local slope is a momentum proxy, not a new signal.",
    "For horizon > 1 in log_return mode, multi-step quantile spreads are combined assuming independent steps.",
    "GARCH baseline is fitted once per fold and filtered forward; a practitioner would refit daily and do slightly better, so the calibration bar is slightly too low.",
    "Synthetic validation series are Gaussian-GARCH; real returns have jumps and fat tails that neither the AR(1) nor the vol baselines capture, which cuts both ways.",
]


def _bars_per_year(bar: str) -> float:
    return float(np.timedelta64(365, "D") / bar_timedelta(bar).to_timedelta64())


def evaluate_forecaster(name, fc, lc, r, samples, folds, cfg: RunConfig, n_tests: int, log):
    H = cfg.forecast.horizon
    pred = np.full(len(samples), np.nan)
    quant = np.full((len(samples), 9), np.nan)
    fold_of = np.full(len(samples), -1)
    for fold in folds:
        assert_no_overlap(samples, fold)
        t0 = time.time()
        fc.fit(r[:fold.train_return_end])
        windows = [context_window(lc, int(t), cfg.forecast.context_len) for t in samples.t[fold.test_sample_idx]]
        d = fc.predict(windows, H).sorted()
        pred[fold.test_sample_idx] = d.point
        quant[fold.test_sample_idx] = d.quantiles
        fold_of[fold.test_sample_idx] = fold.k
        log(f"  [{name}] fold {fold.k}: {len(windows)} pts in {time.time()-t0:.1f}s")
    m = fold_of >= 0
    y_oo, y_cc = samples.y_oo[m], samples.y_cc[m]
    p, q = pred[m], quant[m]
    st = cfg.stats
    rt = cfg.costs.round_trip_frac()
    bpy = _bars_per_year(cfg.data.bar)
    per_fold = []
    for k in sorted(set(fold_of[m])):
        mk = fold_of[m] == k
        side = np.sign(p[mk])
        nz = (side != 0) & (y_oo[mk] != 0)
        hr = float(np.mean(side[nz] == np.sign(y_oo[mk][nz]))) if nz.sum() else np.nan
        net = float(np.mean(side * y_oo[mk] - np.abs(side) * rt))
        per_fold.append({"fold": int(k), "n": int(mk.sum()), "hit_rate": hr, "net_1x": net})
    return {
        "hit_oo": dataclasses.asdict(M.hit_rate(p, y_oo, H, st.n_bootstrap, st.bootstrap_seed, st.alpha, n_tests)),
        "hit_cc": dataclasses.asdict(M.hit_rate(p, y_cc, H, st.n_bootstrap, st.bootstrap_seed + 1, st.alpha, n_tests)),
        "ic_oo": dataclasses.asdict(M.information_coefficient(p, y_oo, H, min(st.n_bootstrap, 500), st.bootstrap_seed + 2, st.alpha)),
        "ic_cc": dataclasses.asdict(M.information_coefficient(p, y_cc, H, min(st.n_bootstrap, 500), st.bootstrap_seed + 3, st.alpha)),
        "pnl_1x": dataclasses.asdict(M.sign_trading_pnl(p, y_oo, rt, 1.0, bpy, H)),
        "pnl_2x": dataclasses.asdict(M.sign_trading_pnl(p, y_oo, rt, 2.0, bpy, H)),
        "calibration": {k: ({str(kk): vv for kk, vv in v.items()} if isinstance(v, dict) else v)
                        for k, v in dataclasses.asdict(M.calibration(y_cc, q)).items()},
        "per_fold": per_fold,
        "_arrays": {"pred": p, "quant": q, "mask": m},
        "_folds": fold_of[m],
    }


def run(cfg: RunConfig, log=print) -> dict:
    t_start = time.time()
    log(f"== Phase 1: {cfg.name} (variant {cfg.variant_hash()})")
    df = load_bars(cfg.data)
    lc = np.log(df["close"].to_numpy(np.float64))
    r = log_returns(lc)
    samples = build_samples(df, cfg.forecast.horizon, cfg.forecast.context_len)
    folds = make_folds(samples, cfg.walkforward)
    for f in folds:
        log("  " + f.describe(samples))

    # Register the hypothesis BEFORE looking at any result.
    ledger = Ledger(cfg.stats.ledger_path)
    n_tests = ledger.record(cfg.variant_hash(), cfg.variant_key())
    log(f"  ledger: this is variant #{n_tests}; Bonferroni alpha = {cfg.stats.alpha/n_tests:.5f}")

    results = {}
    cand_name = cfg.forecast.forecaster
    cand = make_forecaster(cfg.forecast)
    results[cand_name] = evaluate_forecaster(cand_name, cand, lc, r, samples, folds, cfg, n_tests, log)
    for bname, bcls in BASELINES.items():
        if bname == cand_name:
            continue
        results[bname] = evaluate_forecaster(bname, bcls(), lc, r, samples, folds, cfg, n_tests, log)

    mask = results[cand_name]["_arrays"]["mask"]
    y_oo = samples.y_oo[mask]
    rt = cfg.costs.round_trip_frac()
    be1 = M.break_even_hit_rate(y_oo, rt)
    be2 = M.break_even_hit_rate(y_oo, 2 * rt)
    best_const = M.best_constant_sign_rate(y_oo)

    # Turnover-aware, selective evaluation. The hit-rate diagnostic above assumes the
    # worst possible execution of the signal: flip on every bar and pay a full round trip
    # each time. A real implementation holds when the side is unchanged and stands aside
    # when the forecast is small, so the gate must also see the strategy it would run.
    bpy = _bars_per_year(cfg.data.bar)
    for name, r in results.items():
        arr = r["_arrays"]
        z = expanding_standardise(arr["pred"])
        sw = strategy_sweep(z, samples.y_oo[arr["mask"]], rt, bpy,
                            cfg.strategy.taus, cfg.strategy.sizings, n_prior_trials=n_tests,
                            alpha=cfg.strategy.dsr_alpha)
        # per-fold consistency is measured on the WINNING cell, not an arbitrary threshold
        fold_sharpes = []
        for k in sorted(set(r["_folds"])):
            fm = r["_folds"] == k
            seg = sw.best_net[fm]
            fold_sharpes.append(float(_sharpe(seg) * np.sqrt(bpy)) if len(seg) > 10 else 0.0)
        d = dataclasses.asdict(sw)
        d.pop("best_net", None)
        r["strategy"] = {
            "sweep": d, "sharpe_2x": sw.best["sharpe_annual_2x"], "fold_sharpes": fold_sharpes,
            "years_of_data": float(arr["mask"].sum() / bpy),
            "years_to_prove": min_track_record_years(sw.best["sharpe_annual"]),
        }

    candidate = {k: v for k, v in results[cand_name].items() if not k.startswith("_")}
    baselines = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in results.items() if k != cand_name}
    gate = evaluate_gate(candidate, baselines, be1, be2, best_const, cfg.stats.max_mean_abs_coverage_error)
    strat_gate = evaluate_strategy_gate(
        candidate["strategy"], {k: v["strategy"] for k, v in baselines.items() if k not in ("zero", "ewma", "garch")},
        cfg.strategy.dsr_alpha)

    ledger.record(cfg.variant_hash(), cfg.variant_key(), {
        "hit_rate_oo": candidate["hit_oo"]["hit_rate"], "p_value": candidate["hit_oo"]["p_value"],
        "ci_lo_adj": candidate["hit_oo"]["ci_lo_adj"], "break_even_1x": be1, "verdict": gate.verdict,
    })

    out_dir = Path(cfg.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"reliability_{cfg.name}.png"
    reliability_diagram({cand_name: candidate["calibration"]["quantile_coverage"],
                         **{k: v["calibration"]["quantile_coverage"] for k, v in baselines.items() if k in ("garch", "ewma")}}, png)

    res = {
        "name": cfg.name, "generated_at": datetime.now(timezone.utc).isoformat(), "variant_hash": cfg.variant_hash(),
        "config": cfg.to_dict(), "n_bars": int(len(df)), "first_bar": str(df["open_time"].iloc[0]), "last_bar": str(df["open_time"].iloc[-1]),
        "years_covered": float((df["open_time"].iloc[-1] - df["open_time"].iloc[0]).days / 365.25),
        "n_test_points": int(mask.sum()), "round_trip_bps": cfg.costs.round_trip_bps(),
        "mean_abs_move_bps": float(1e4 * np.mean(np.abs(y_oo))),
        "break_even_1x": be1, "break_even_2x": be2, "best_constant_sign": best_const,
        "ledger_count": n_tests, "ledger_summary": ledger.holm_bh_summary(cfg.stats.alpha),
        "candidate": candidate, "baselines": baselines, "per_fold": candidate["per_fold"],
        "gate": dataclasses.asdict(gate), "strategy_gate": dataclasses.asdict(strat_gate),
        "reliability_png": png.name, "assumptions": ASSUMPTIONS,
        "runtime_s": time.time() - t_start,
    }
    if hasattr(cand, "n_model_calls"):
        res["timesfm_model_calls"] = cand.n_model_calls
        res["timesfm_cache_hits"] = cand.n_cache_hits
    save_json(res, out_dir / f"phase1_{cfg.name}.json")
    write_report(res, out_dir / f"phase1_{cfg.name}.md")
    log(f"== hit-rate verdict: {gate.verdict}")
    for rr in gate.reasons:
        log("   - " + rr)
    log(f"== strategy verdict (turnover-aware, selective): {strat_gate.verdict}")
    for rr in strat_gate.reasons:
        log("   - " + rr)
    log(f"== report: {out_dir / f'phase1_{cfg.name}.md'}  ({res['runtime_s']:.0f}s)")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--forecaster", help="override forecast.forecaster (counts as a new variant)")
    ap.add_argument("--input-mode", help="override forecast.input_mode (counts as a new variant)")
    ap.add_argument("--context-len", type=int, help="override forecast.context_len (counts as a new variant)")
    ap.add_argument("--horizon", type=int, help="override forecast.horizon (counts as a new variant)")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    over = {k: v for k, v in {"forecaster": a.forecaster, "input_mode": a.input_mode, "context_len": a.context_len, "horizon": a.horizon}.items() if v is not None}
    if over:
        cfg = dataclasses.replace(cfg, forecast=dataclasses.replace(cfg.forecast, **over),
                                  name=cfg.name + "_" + "_".join(f"{k}={v}" for k, v in over.items()))
    run(cfg)


if __name__ == "__main__":
    main()
