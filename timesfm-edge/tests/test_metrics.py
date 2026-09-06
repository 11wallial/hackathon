import numpy as np
import pytest

from tfm_edge.analysis import metrics as M
from tfm_edge.model.base import QUANTILE_LEVELS, normal_quantiles


def test_hit_rate_ci_covers_truth_on_coin_flips():
    rng = np.random.default_rng(0)
    covered = 0
    trials = 40
    for i in range(trials):
        y = rng.standard_normal(2000)
        pred = rng.standard_normal(2000)          # no skill: true hit rate 0.5
        r = M.hit_rate(pred, y, horizon=1, n_boot=400, seed=i, alpha=0.05, n_tests=1)
        covered += r.ci_lo <= 0.5 <= r.ci_hi
    assert covered >= 0.85 * trials


def test_bonferroni_bound_is_lower():
    rng = np.random.default_rng(1)
    y = rng.standard_normal(3000)
    pred = y + 3 * rng.standard_normal(3000)
    r1 = M.hit_rate(pred, y, 1, 500, 0, 0.05, n_tests=1)
    r20 = M.hit_rate(pred, y, 1, 500, 0, 0.05, n_tests=20)
    assert r20.ci_lo_adj < r1.ci_lo_adj < r1.hit_rate


def test_break_even_formula():
    y = np.array([0.003, -0.003, 0.003, -0.003])
    assert np.isclose(M.break_even_hit_rate(y, 0.0015), 0.75)
    assert np.isclose(M.break_even_hit_rate(y, 0.0), 0.5)


def test_best_constant_sign():
    assert M.best_constant_sign_rate(np.array([1, 1, 1, -1.0])) == 0.75


def test_calibration_correct_sigma_beats_wrong_sigma():
    rng = np.random.default_rng(2)
    y = rng.standard_normal(20000) * 0.01
    mu = np.zeros_like(y)
    good = M.calibration(y, normal_quantiles(mu, np.full_like(y, 0.01)))
    wide = M.calibration(y, normal_quantiles(mu, np.full_like(y, 0.02)))
    tight = M.calibration(y, normal_quantiles(mu, np.full_like(y, 0.005)))
    assert good.mean_abs_coverage_error < 0.015
    assert good.pinball_loss < wide.pinball_loss and good.pinball_loss < tight.pinball_loss
    assert wide.interval_coverage[0.8] > 0.9 and tight.interval_coverage[0.8] < 0.6
    for k, l in enumerate(QUANTILE_LEVELS):
        assert abs(good.quantile_coverage[float(l)] - l) < 0.015


def test_sign_pnl_costs_scale():
    rng = np.random.default_rng(3)
    y = rng.standard_normal(1000) * 0.003
    pred = rng.standard_normal(1000)
    p1 = M.sign_trading_pnl(pred, y, 0.0015, 1.0, 8760, 1)
    p2 = M.sign_trading_pnl(pred, y, 0.0015, 2.0, 8760, 1)
    assert np.isclose(p1.mean_net_per_bar - p2.mean_net_per_bar, 0.0015)
    assert p1.trade_fraction == 1.0
