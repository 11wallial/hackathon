"""Live (or paper) performance against what the backtest construction predicts for the same days.

Two comparisons, because they answer different questions:

1. ACTUAL vs SHADOW  (implementation shortfall)
   The shadow book is the IDEAL weights the decision function chose, held exactly, with no
   whole-share rounding, no rejected orders and no stops, earning the realised open and close
   prices, minus the modelled cost on its turnover. Whatever separates the account from its
   shadow is the cost of actually trading: rounding, slippage worse than modelled, fills that
   did not happen, brackets that fired, borrow costs. If this gap is large or drifting, the
   backtest's costs and fills are not describing reality, whatever the signal does.

2. SHADOW/ACTUAL vs BACKTEST EXPECTATION  (is the edge there?)
   The Phase 1 report predicts a mean net return per day for the winning configuration. After
   n live days, is the realised mean consistent with it? This is a z-score, and with the few
   days a first trial has it is wide: a handful of days cannot confirm an edge, it can only
   contradict one.

HOW THE SHADOW EARNS (open-to-open holds, measured close-to-close)
   Weights decided at the close of d-1 are held from the OPEN of d. So day d's return is
       sum_i W_prev(i) * (open_d / close_{d-1} - 1)      the overnight gap, still in last day's book
     + sum_i W_d(i)   * (close_d / open_d - 1)           the new book, open to close
     - turnover(W_d vs W_prev) * round_trip_cost / 2
   which is the same open-to-open economics as the backtest, just cut at the close so it lines
   up with end-of-day account equity.

KNOWN OMISSIONS: dividends, short borrow fees and financing are in neither series' model but are
in the account's equity, so they appear as divergence. For hard-to-borrow shorts that can matter.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..data.panel import Panel


def _dates(panel: Panel) -> list[str]:
    return [str(np.datetime_as_string(t, unit="D")) for t in panel.open_time]


def shadow_returns(ideal: dict[str, dict[str, float]], panel: Panel, round_trip_frac: float,
                   sessions: list[str]) -> dict[str, float]:
    """Daily return of the ideal book, as a fraction of capital, for each session in `sessions`."""
    dates = _dates(panel)
    idx = {d: i for i, d in enumerate(dates)}
    sym = {s: a for a, s in enumerate(panel.symbols)}
    op, cl = np.exp(panel.log_open), np.exp(panel.log_close)
    out: dict[str, float] = {}
    prev_w: dict[str, float] | None = None
    ideal_dates = sorted(ideal)
    for d in sorted(set(sessions) | set(ideal_dates)):
        if d not in idx:
            continue
        w = ideal.get(d)
        if w is None:
            w = prev_w if prev_w is not None else {}                # no plan that day: the book was held
        i = idx[d]
        if prev_w is not None and i >= 1 and d in sessions:
            r = 0.0
            for s, ws in prev_w.items():
                a = sym.get(s)
                if a is not None and np.isfinite(op[i, a]) and np.isfinite(cl[i - 1, a]):
                    r += ws * (op[i, a] / cl[i - 1, a] - 1.0)
            for s, ws in w.items():
                a = sym.get(s)
                if a is not None and np.isfinite(cl[i, a]) and np.isfinite(op[i, a]):
                    r += ws * (cl[i, a] / op[i, a] - 1.0)
            names = set(w) | set(prev_w)
            turnover = sum(abs(w.get(s, 0.0) - prev_w.get(s, 0.0)) for s in names)
            out[d] = r - turnover * round_trip_frac / 2.0
        prev_w = w
    return out


def backtest_expectation(base_dir: str, forecaster: str, model_id: str) -> dict | None:
    """The newest real-data Phase 1 report for this model: its predicted mean and spread per day."""
    best = None
    for p in sorted(Path(base_dir, "reports").glob("xs_*.json")):
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        cfg = d.get("config", {})
        if cfg.get("data", {}).get("source") in ("synthetic", None):
            continue
        fc = cfg.get("forecast", {})
        if fc.get("forecaster") != forecaster or fc.get("model_id") != model_id:
            continue
        if best is None or d.get("generated_at", "") > best.get("generated_at", ""):
            best = d
    if best is None:
        return None
    b = best["candidate"]["sweep"]["best"]
    bpy = best.get("decisions_per_year") or best.get("bars_per_year") or 252.0
    sharpe = b.get("sharpe_annual", 0.0)
    mean_bps = b["mean_net_bps"]
    sd_bps = abs(mean_bps / (sharpe / np.sqrt(bpy))) if sharpe else None
    return {"report": best["name"], "verdict": best["gate"]["verdict"], "mean_bps": mean_bps,
            "sd_bps": sd_bps, "sharpe": sharpe}


def compute(store, panel: Panel, *, capital: float, round_trip_frac: float,
            expectation: dict | None = None) -> dict:
    eq = store.equity_by_session()
    ideal = store.ideal_weights()
    out: dict = {"n": 0, "dates": [], "actual_cum_bps": [], "shadow_cum_bps": [], "expectation": expectation}
    if len(eq) < 2 or not ideal:
        out["note"] = "need at least two sessions of equity and one plan"
        return out
    sessions = [e["session"] for e in eq]
    e_by = {e["session"]: e["equity"] for e in eq}
    first_ideal = min(ideal)
    shadow = shadow_returns(ideal, panel, round_trip_frac, sessions)
    pairs = []
    for a, b in zip(sessions, sessions[1:]):
        if b >= first_ideal and b in shadow:
            pairs.append((b, (e_by[b] - e_by[a]) / capital, shadow[b]))
    if not pairs:
        out["note"] = "no overlapping sessions yet"
        return out
    d, act, sh = (np.array(x) for x in zip(*[(p[0], p[1], p[2]) for p in pairs]))
    diff = act - sh
    n = len(pairs)
    out.update(
        n=n, dates=[p[0] for p in pairs],
        actual_cum_bps=[float(x) for x in np.cumsum(act) * 1e4],
        shadow_cum_bps=[float(x) for x in np.cumsum(sh) * 1e4],
        mean_actual_bps=float(act.mean() * 1e4), mean_shadow_bps=float(sh.mean() * 1e4),
        mean_gap_bps=float(diff.mean() * 1e4), sd_gap_bps=float(diff.std(ddof=1) * 1e4) if n > 2 else None,
        cum_gap_bps=float(diff.sum() * 1e4),
        corr=float(np.corrcoef(act, sh)[0, 1]) if n > 2 and act.std() > 0 and sh.std() > 0 else None,
    )
    out["z_gap"] = (float(diff.mean() / (diff.std(ddof=1) / np.sqrt(n)))
                    if n > 2 and diff.std(ddof=1) > 0 else None)
    if expectation and expectation.get("sd_bps"):
        out["z_vs_backtest"] = float((out["mean_actual_bps"] - expectation["mean_bps"])
                                     / (expectation["sd_bps"] / np.sqrt(n)))
    return out


def write_daily_report(result: dict, path: Path, *, mode: str, name: str) -> None:
    L = [f"# Daily divergence report: {name}", "", f"Mode: **{mode}**. Sessions compared: **{result['n']}**.", ""]
    if not result["n"]:
        L.append(result.get("note", "nothing to compare yet"))
    else:
        L += ["| | per day (bps of capital) |", "|---|---|",
              f"| actual (account) | {result['mean_actual_bps']:+.2f} |",
              f"| shadow (ideal book, modelled costs) | {result['mean_shadow_bps']:+.2f} |",
              f"| **gap (actual - shadow)** | **{result['mean_gap_bps']:+.2f}** |", "",
              f"Cumulative gap: **{result['cum_gap_bps']:+.1f} bps**. "
              + (f"Correlation of daily returns: {result['corr']:.2f}. " if result.get("corr") is not None else ""),
              (f"Gap z-score: {result['z_gap']:+.2f} (is the shortfall systematic?)." if result.get("z_gap") is not None else "")]
        ex = result.get("expectation")
        if ex:
            L += ["", f"Backtest expectation ({ex['report']}, verdict {ex['verdict']}): {ex['mean_bps']:+.2f} bps/day.",
                  (f"Realised vs expected z: **{result['z_vs_backtest']:+.2f}**." if "z_vs_backtest" in result else "")]
        else:
            L += ["", "No real-data Phase 1 report exists for this model, so there is no backtest expectation to "
                      "compare against. The shadow comparison above is still valid."]
        L += ["", "A few days cannot confirm an edge; they can only contradict one. Read the gap first: "
                  "a large or growing gap means the costs and fills the backtest assumed are not what you are getting."]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(l for l in L if l is not None) + "\n")
