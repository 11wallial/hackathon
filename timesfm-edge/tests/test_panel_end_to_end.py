"""The cross-sectional pipeline must find a planted cross-sectional edge and must find
nothing when there is nothing to find."""
import dataclasses

from tfm_edge.analysis.panel_run import run
from tfm_edge.config import (CostModel, CrossSectionConfig, DataConfig, ForecastConfig,
                             RunConfig, StatsConfig, StrategyConfig, WalkForwardConfig)


def _cfg(tmp_path, phi, seed, name, costs=CostModel(0.2, 0.8, 0.5)):
    return RunConfig(
        name=name,
        data=DataConfig(source="synthetic", synthetic_n=1600, synthetic_seed=seed, bar="1d"),
        cross_section=CrossSectionConfig(enabled=True, n_assets=40, residualise="beta",
                                         synthetic_phi_idio=phi),
        forecast=ForecastConfig(forecaster="ar1", context_len=128, horizon=1),
        walkforward=WalkForwardConfig(n_splits=4, embargo_bars=5, min_train_bars=400),
        strategy=StrategyConfig(top_fractions=(0.2, 0.3), smoothing_halflives=(0.0, 5.0),
                                rebalance_intervals=(1,)),
        costs=costs, stats=StatsConfig(ledger_path=str(tmp_path / "ledger.json")),
        report_dir=str(tmp_path),
    )


def test_no_edge_panel_stops(tmp_path):
    res = run(_cfg(tmp_path, 0.0, 31, "null"), log=lambda *a: None)
    assert res["gate"]["verdict"] == "STOP"
    assert abs(res["candidate"]["cross_sectional_ic"]) < 0.02
    assert (tmp_path / "xs_null.md").exists()


def test_planted_cross_sectional_edge_is_found(tmp_path):
    res = run(_cfg(tmp_path, 0.08, 32, "edge"), log=lambda *a: None)
    c = res["candidate"]
    assert c["cross_sectional_ic"] > 0.03
    assert c["sweep"]["best"]["sharpe_annual"] > 0.5
    assert res["gate"]["verdict"].startswith("PROCEED")


def test_expensive_costs_kill_the_same_edge(tmp_path):
    """Identical panel and identical signal, crypto taker fees instead of equity fees."""
    cheap = run(_cfg(tmp_path, 0.08, 32, "cheap"), log=lambda *a: None)
    dear = run(_cfg(tmp_path, 0.08, 32, "dear", costs=CostModel(5.0, 0.5, 2.0)), log=lambda *a: None)
    assert dear["candidate"]["sweep"]["best"]["sharpe_annual"] < cheap["candidate"]["sweep"]["best"]["sharpe_annual"]
    assert dear["candidate"]["sharpe_2x"] < cheap["candidate"]["sharpe_2x"]
