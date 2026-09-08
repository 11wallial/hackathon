"""The harness must (a) find nothing on a martingale and (b) find a planted edge."""
import dataclasses

import numpy as np

from tfm_edge.analysis.phase1 import run
from tfm_edge.config import DataConfig, ForecastConfig, RunConfig, StatsConfig, WalkForwardConfig


def _cfg(tmp_path, kind, phi, seed, name):
    return RunConfig(
        name=name,
        data=DataConfig(source="synthetic", synthetic_kind=kind, synthetic_phi=phi, synthetic_n=9000, synthetic_seed=seed),
        forecast=ForecastConfig(forecaster="ar1", context_len=256, horizon=1),
        walkforward=WalkForwardConfig(n_splits=4, embargo_bars=12, min_train_bars=2000),
        stats=StatsConfig(n_bootstrap=300, ledger_path=str(tmp_path / "ledger.json")),
        report_dir=str(tmp_path),
    )


def test_random_walk_has_no_edge(tmp_path):
    res = run(_cfg(tmp_path, "random_walk", 0.0, 11, "rw"), log=lambda *_: None)
    hr = res["candidate"]["hit_oo"]
    assert hr["ci_lo"] < 0.5 < hr["ci_hi"] + 0.01
    assert res["gate"]["verdict"] in ("STOP", "VOL_MODEL_ONLY")
    assert (tmp_path / "phase1_rw.md").exists()


def test_planted_ar1_edge_is_found(tmp_path):
    res = run(_cfg(tmp_path, "ar1", 0.15, 12, "ar1"), log=lambda *_: None)
    hr = res["candidate"]["hit_oo"]
    theory = 0.5 + np.arcsin(0.15) / np.pi
    assert hr["ci_lo"] > 0.5
    assert abs(hr["hit_rate"] - theory) < 0.02
    assert res["candidate"]["ic_oo"]["ci_lo"] > 0
    # and still not tradable at 15 bps round trip: that is the honest answer
    assert hr["ci_lo_adj"] < res["break_even_1x"]
    assert res["ledger_count"] == 1


def test_ledger_count_grows_with_variants(tmp_path):
    c = _cfg(tmp_path, "random_walk", 0.0, 13, "v1")
    run(c, log=lambda *_: None)
    c2 = dataclasses.replace(c, name="v2", forecast=dataclasses.replace(c.forecast, horizon=2))
    res = run(c2, log=lambda *_: None)
    assert res["ledger_count"] == 2
    res = run(c2, log=lambda *_: None)     # same variant again: still 2
    assert res["ledger_count"] == 2
