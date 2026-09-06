"""Same edge, same data, different setups. Which configurations can pay for themselves?

    python -m tfm_edge.analysis.compare_setups

One synthetic panel with a small, purely idiosyncratic, purely cross-sectional edge is
generated once. Every row below trades THAT SAME EDGE a different way. Nothing about the
signal changes between rows: only the instrument count, the bar, the cost, the
residualisation and the turnover control. The spread of outcomes is therefore entirely
attributable to setup, which is the point.

This is the answer to "is there a setup that works": yes, and it is not a better model.
"""
from __future__ import annotations

import dataclasses
import io
import contextlib
from pathlib import Path

import numpy as np

import pandas as pd

from ..config import (CostModel, CrossSectionConfig, DataConfig, ForecastConfig, RunConfig,
                      StatsConfig, StrategyConfig, WalkForwardConfig)
from ..data.panel import generate_panel
from . import panel_run, phase1
from .feasibility import evaluate, format_survey, survey

PHI = 0.06          # planted idiosyncratic AR(1); small, and identical in every row
N_BARS = 2600
N_ASSETS = 60


def _cfg(name, *, n_assets, bar, costs, residualise, ledger, seed=21, smoothing=(0.0, 2.0, 5.0, 10.0)):
    return RunConfig(
        name=name,
        data=DataConfig(source="synthetic", synthetic_n=N_BARS, synthetic_seed=seed, bar=bar),
        cross_section=CrossSectionConfig(enabled=True, n_assets=n_assets, residualise=residualise,
                                         synthetic_phi_idio=PHI),
        forecast=ForecastConfig(forecaster="ar1", context_len=256, horizon=1),
        walkforward=WalkForwardConfig(n_splits=6, embargo_bars=5, min_train_bars=600),
        strategy=StrategyConfig(smoothing_halflives=smoothing),
        costs=costs, stats=StatsConfig(ledger_path=ledger), report_dir="reports/compare",
    )


CRYPTO_TAKER = CostModel(commission_bps=5.0, half_spread_bps=0.5, slippage_bps=2.0)   # 15 bps rt
CRYPTO_MAKER = CostModel(commission_bps=2.0, half_spread_bps=0.0, slippage_bps=0.0)   # 4 bps rt
EQUITY = CostModel(commission_bps=0.2, half_spread_bps=0.8, slippage_bps=0.5)         # 3 bps rt

SETUPS = [
    ("60 assets, daily, taker, no residual",    dict(n_assets=60, bar="1d", costs=CRYPTO_TAKER, residualise="none")),
    ("60 assets, daily, taker, beta residual",  dict(n_assets=60, bar="1d", costs=CRYPTO_TAKER, residualise="beta")),
    ("60 assets, daily, maker, beta residual",  dict(n_assets=60, bar="1d", costs=CRYPTO_MAKER, residualise="beta")),
    ("60 assets, daily, equity cost, residual", dict(n_assets=60, bar="1d", costs=EQUITY,       residualise="beta")),
]


def _single_asset_row(ledger: str, log) -> dict:
    """One column of the SAME panel, traded on its own. This is the setup the original
    harness was pointed at: no cross-section, no market neutrality, no breadth."""
    d = Path("reports/compare")
    d.mkdir(parents=True, exist_ok=True)
    panel = generate_panel(N_BARS, N_ASSETS, bar="1d", seed=21, phi_idio=PHI)
    csv = d / "single_asset.csv"
    pd.DataFrame({
        "open_time": panel.open_time,
        "open": np.exp(panel.log_open[:, 0]), "high": np.exp(panel.log_close[:, 0]) * 1.01,
        "low": np.exp(panel.log_close[:, 0]) * 0.99, "close": np.exp(panel.log_close[:, 0]),
        "volume": 1.0,
    }).to_csv(csv, index=False)
    cfg = RunConfig(
        name="single_asset_daily",
        data=DataConfig(source="csv", csv_path=str(csv), bar="1d"),
        forecast=ForecastConfig(forecaster="ar1", context_len=256, horizon=1),
        walkforward=WalkForwardConfig(n_splits=6, embargo_bars=5, min_train_bars=600),
        costs=CRYPTO_TAKER, stats=StatsConfig(ledger_path=ledger, n_bootstrap=400),
        report_dir="reports/compare",
    )
    with contextlib.redirect_stdout(io.StringIO()):
        res = phase1.run(cfg, log=lambda *a: None)
    st = res["candidate"]["strategy"]
    return {"setup": "1 asset, daily, crypto taker", "ic": res["candidate"]["ic_oo"]["ic"],
            "sharpe": st["sweep"]["best"]["sharpe_annual"], "sharpe_2x": st["sharpe_2x"],
            "turnover": st["sweep"]["best"]["turnover_per_bar"],
            "dsr": st["sweep"]["dsr"]["deflated_sharpe"],
            "years_need": st["years_to_prove"], "years_have": st["years_of_data"],
            "verdict": res["strategy_gate"]["verdict"]}


def run_all(log=print) -> list[dict]:
    Path("reports/compare").mkdir(parents=True, exist_ok=True)
    ledger = "reports/compare/ledger_compare.json"
    out = [_single_asset_row(ledger, log)]
    log(f"  {out[0]['setup']:42s} -> {out[0]['verdict']}")
    for label, kw in SETUPS:
        cfg = _cfg(label.replace(" ", "_").replace(",", ""), ledger=ledger, **kw)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                res = panel_run.run(cfg, log=lambda *a: None)
            c = res["candidate"]
            out.append({"setup": label, "ic": c["cross_sectional_ic"],
                        "sharpe": c["sweep"]["best"]["sharpe_annual"],
                        "sharpe_2x": c["sharpe_2x"],
                        "turnover": c["sweep"]["best"]["turnover_per_bar"],
                        "dsr": c["sweep"]["dsr"]["deflated_sharpe"],
                        "years_need": c["years_to_prove"], "years_have": c["years_of_data"],
                        "verdict": res["gate"]["verdict"]})
        except Exception as e:                                  # a 1-asset "cross-section" cannot form a book
            out.append({"setup": label, "ic": float("nan"), "sharpe": float("nan"),
                        "sharpe_2x": float("nan"), "turnover": float("nan"), "dsr": float("nan"),
                        "years_need": float("nan"), "years_have": float("nan"),
                        "verdict": f"N/A ({type(e).__name__})"})
        log(f"  {label:42s} -> {out[-1]['verdict']}")
    return out


def format_table(rows: list[dict]) -> str:
    L = ["| setup | cross-sec IC | Sharpe | Sharpe 2x | turnover/bar | DSR | years needed / have | verdict |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda x, d=3: "-" if not np.isfinite(x) else f"{x:.{d}f}"
        yrs = "-" if not np.isfinite(r["years_need"]) else f"{r['years_need']:.1f} / {r['years_have']:.1f}"
        L.append(f"| {r['setup']} | {f(r['ic'],4)} | {f(r['sharpe'],2)} | {f(r['sharpe_2x'],2)} | "
                 f"{f(r['turnover'],2)} | {f(r['dsr'],4)} | {yrs} | `{r['verdict']}` |")
    return "\n".join(L)


def main(argv=None):
    print(f"Same panel, same planted edge (idiosyncratic AR(1) phi={PHI}), {N_BARS} daily bars.")
    print("Only the setup changes.\n")
    rows = run_all()
    print()
    print(format_table(rows))
    print()
    print(format_survey(survey(ic=0.03), ic=0.03))


if __name__ == "__main__":
    main()
