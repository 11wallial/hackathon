"""Markdown report and reliability diagram for a Phase 1 run."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..model.base import QUANTILE_LEVELS

SPURIOUS = """\
## What would have to be true for a positive result here to be spurious

1. **A leak survived the tests.** `tests/test_no_lookahead.py` shifts labels and checks the
   harness catches it, but a leak in the *data feed* (e.g. a venue that restates closes, or a
   CSV with close-timestamps mislabelled as opens) is invisible to those tests. Verify the
   feed's timestamp convention by hand against a second source.
2. **Selection across the ledger.** The Bonferroni bound only covers variants recorded in
   `experiment_ledger.json`. Any variant tried elsewhere (a notebook, a deleted ledger, a
   different repo) is uncounted and the true N is larger.
3. **Regime luck.** {n_splits} forward-chained folds over {years:.1f} years is still one draw of
   history. A hit rate that comes from two folds and is flat elsewhere is a regime, not an edge.
   Check the per-fold table below.
4. **Cost model too kind.** Costs assume small size and passive fills at the open. If real
   fills are worse than the 2x row, the 2x row is the optimistic one.
5. **|move| is not independent of correctness.** The break-even formula assumes it is. If the
   model is wrong mostly on large moves (typical: it is slow to react to jumps), the true
   break-even hit rate is above the number printed here.
6. **Bootstrap block length too short.** Blocks of {block_len} bars may not span the
   dependence in hourly crypto vol clusters; a longer block widens the interval.
"""


def reliability_diagram(qcov_by_model: dict[str, dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for name, qc in qcov_by_model.items():
        levels = sorted(float(k) for k in qc)
        ax.plot(levels, [qc[l] if l in qc else qc[str(l)] for l in levels], marker="o", label=name)
    ax.set_xlabel("nominal quantile level")
    ax.set_ylabel("empirical P(y <= q)")
    ax.set_title("Reliability (Test B)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _f(x, d=4):
    return "nan" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def write_report(res: dict, out_md: Path) -> None:
    c = res["candidate"]
    b = res["baselines"]
    g = res["gate"]
    cfg = res["config"]
    lines = []
    lines.append(f"# Phase 1 report: {res['name']}\n")
    lines.append(f"Generated {res['generated_at']}. Config hash `{res['variant_hash']}`.\n")
    lines.append(f"**Verdict: `{g['verdict']}`**  (Test A {'PASS' if g['test_a_pass'] else 'FAIL'}, "
                 f"Test A at 2x costs {'PASS' if g['test_a_pass_2x'] else 'FAIL'}, Test B {'PASS' if g['test_b_pass'] else 'FAIL'})\n")
    for r in g["reasons"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Setup\n")
    d, f, w = cfg["data"], cfg["forecast"], cfg["walkforward"]
    lines.append(f"- Data: `{d['source']}` {d['symbol'] if d['source']!='synthetic' else d['synthetic_kind']} {d['bar']} bars, "
                 f"{res['n_bars']} bars from {res['first_bar']} to {res['last_bar']}")
    lines.append(f"- Candidate: `{f['forecaster']}` model `{f['model_id'] if f['forecaster']=='timesfm' else '-'}` input `{f['input_mode']}` context {f['context_len']} horizon {f['horizon']} bar(s)")
    lines.append(f"- Walk-forward: {w['n_splits']} forward-chained folds, purge = horizon, embargo {w['embargo_bars']} bars, "
                 f"{res['n_test_points']} out-of-sample decision points")
    lines.append(f"- Costs (per side bps): commission {cfg['costs']['commission_bps']}, half-spread {cfg['costs']['half_spread_bps']}, "
                 f"slippage {cfg['costs']['slippage_bps']}; round trip {res['round_trip_bps']:.1f} bps (1x), {2*res['round_trip_bps']:.1f} bps (2x)")
    lines.append(f"- Mean |tradable {f['horizon']}-bar return|: {res['mean_abs_move_bps']:.1f} bps")
    lines.append(f"- **Break-even hit rate: {res['break_even_1x']:.4f} (1x), {res['break_even_2x']:.4f} (2x)**")
    lines.append(f"- **Configuration variants in ledger (N for adjustment): {res['ledger_count']}**; this run's adjusted alpha = {cfg['stats']['alpha']}/{res['ledger_count']} = {cfg['stats']['alpha']/res['ledger_count']:.5f}")
    lines.append(f"- Ledger-wide survivors: Holm {len(res['ledger_summary']['holm_survivors'])}, BH {len(res['ledger_summary']['bh_survivors'])} of {res['ledger_summary']['n']} variants with p-values")
    lines.append("")
    lines.append("## Test A: directional edge (tradable open-to-open return)\n")
    lines.append("| forecaster | n | hit rate | 95% CI | adj. lower bound | p (one-sided) | IC (Spearman) | IC 95% CI | trade frac | net/bar 1x (bps) | Sharpe 1x | net/bar 2x (bps) | Sharpe 2x |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = [("**" + f["forecaster"] + " (candidate)**", c)] + [(k, v) for k, v in b.items()]
    for name, r in rows:
        h, ic = r["hit_oo"], r["ic_oo"]
        p1, p2 = r["pnl_1x"], r["pnl_2x"]
        lines.append(f"| {name} | {h['n']} | {_f(h['hit_rate'])} | [{_f(h['ci_lo'])}, {_f(h['ci_hi'])}] | {_f(h['ci_lo_adj'])} | {_f(h['p_value'])} | "
                     f"{_f(ic['ic'])} | [{_f(ic['ci_lo'])}, {_f(ic['ci_hi'])}] | {_f(p1['trade_fraction'],2)} | {_f(1e4*p1['mean_net_per_bar'],2)} | {_f(p1['sharpe_annualised'],2)} | "
                     f"{_f(1e4*p2['mean_net_per_bar'],2)} | {_f(p2['sharpe_annualised'],2)} |")
    lines.append("")
    lines.append(f"Best constant-sign rate (always long or always short): {res['best_constant_sign']:.4f}. "
                 f"Break-even: {res['break_even_1x']:.4f} (1x) / {res['break_even_2x']:.4f} (2x).\n")
    lines.append("Same statistics on the forecast target (close-to-close), for reference only; you cannot trade this:\n")
    lines.append("| forecaster | hit rate cc | 95% CI | IC cc |")
    lines.append("|---|---|---|---|")
    for name, r in rows:
        h = r["hit_cc"]
        lines.append(f"| {name} | {_f(h['hit_rate'])} | [{_f(h['ci_lo'])}, {_f(h['ci_hi'])}] | {_f(r['ic_cc']['ic'])} |")
    lines.append("")
    lines.append("### Per-fold candidate hit rate (tradable)\n")
    lines.append("| fold | n | hit rate | mean net/bar 1x (bps) |")
    lines.append("|---|---|---|---|")
    for fr in res["per_fold"]:
        lines.append(f"| {fr['fold']} | {fr['n']} | {_f(fr['hit_rate'])} | {_f(1e4*fr['net_1x'],2)} |")
    lines.append("")
    lines.append("## Test B: calibration (forecast target, close-to-close)\n")
    lines.append("| forecaster | 20% cov | 40% cov | 60% cov | 80% cov | mean abs cov err | pinball (mean, 1e-4) | CRPS proxy (1e-4) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name, r in rows:
        cal = r["calibration"]
        ic = cal["interval_coverage"]
        lines.append(f"| {name} | {_f(ic['0.2'],3)} | {_f(ic['0.4'],3)} | {_f(ic['0.6'],3)} | {_f(ic['0.8'],3)} | {_f(cal['mean_abs_coverage_error'],4)} | "
                     f"{_f(1e4*cal['pinball_loss'],4)} | {_f(1e4*cal['crps_proxy'],4)} |")
    lines.append("")
    lines.append("Per-quantile empirical coverage P(y <= q_level):\n")
    lines.append("| forecaster | " + " | ".join(f"q{l:.1f}" for l in QUANTILE_LEVELS) + " |")
    lines.append("|---|" + "---|" * len(QUANTILE_LEVELS))
    for name, r in rows:
        qc = r["calibration"]["quantile_coverage"]
        lines.append(f"| {name} | " + " | ".join(_f(qc[str(float(l))], 3) for l in QUANTILE_LEVELS) + " |")
    lines.append("")
    lines.append(f"![reliability]({res['reliability_png']})\n")
    lines.append(SPURIOUS.format(n_splits=w["n_splits"], years=res["years_covered"], block_len=c["hit_oo"]["block_len"]))
    lines.append("## Assumptions most likely to be wrong\n")
    for a in res["assumptions"]:
        lines.append(f"- {a}")
    lines.append("")
    out_md.write_text("\n".join(lines))


def save_json(res: dict, path: Path) -> None:
    path.write_text(json.dumps(res, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
