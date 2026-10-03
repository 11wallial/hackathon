import numpy as np
import pytest

from tfm_edge.analysis.panel_run import (cross_sectional_scores, hold_between_rebalances,
                                         smooth_scores)
from tfm_edge.data.panel import generate_panel
from tfm_edge.features.cross_section import (book_pnl, build_book, build_panel_samples,
                                             cross_sectional_weights, estimate_betas,
                                             neutralise_targets, residual_log_close)


@pytest.fixture(scope="module")
def panel():
    return generate_panel(1500, 40, phi_idio=0.08, seed=5)


def test_panel_targets_start_after_execution(panel):
    s = build_panel_samples(panel, horizon=2, context_len=64)
    t = s.t[100]
    assert np.allclose(s.y_cc[100], panel.log_close[t + 2] - panel.log_close[t])
    assert np.allclose(s.y_oo[100], panel.log_open[t + 3] - panel.log_open[t + 1])


def test_book_is_dollar_neutral_and_bounded():
    w = cross_sectional_weights(np.arange(50.0), top_fraction=0.2, gross=1.0)
    assert np.isclose(w.sum(), 0.0)
    assert np.isclose(np.abs(w).sum(), 1.0)
    assert (w > 0).sum() == (w < 0).sum() == 10
    assert w[-1] > 0 and w[0] < 0          # long the highest score, short the lowest


def test_residualisation_raises_ic_and_lowers_target_vol(panel):
    """The market factor is unpredictable. Removing it from both the model input and the
    target raises the achievable IC and shrinks the volatility the edge must overcome."""
    s = build_panel_samples(panel, 1, 128)
    betas = estimate_betas(panel.returns(), 800)
    ics, vols = {}, {}
    for mode in ("none", "beta"):
        series = residual_log_close(panel, betas, mode)
        signal = np.diff(series, axis=0)[s.t - 1]
        target = neutralise_targets(s.y_cc, betas, mode)
        ics[mode] = float(np.corrcoef(signal.ravel(), target.ravel())[0, 1])
        vols[mode] = float(target.std())
    assert ics["beta"] > ics["none"]
    assert vols["beta"] < vols["none"]


def test_panel_training_array_must_be_asset_contiguous(panel):
    """Regression: raveling a (bars, assets) matrix row-major puts different assets at
    the SAME bar next to each other, so an AR(1) fitted on it measures cross-sectional
    correlation rather than autocorrelation and comes out badly wrong."""
    d = np.diff(panel.log_close, axis=0)

    def phi(x):
        a, b = x[:-1], x[1:]
        return float(np.linalg.lstsq(np.column_stack([np.ones_like(a), a]), b, rcond=None)[0][1])

    wrong, right = phi(d.ravel()), phi(d.ravel(order="F"))
    assert abs(right - 0.08) < 0.05
    assert abs(wrong - 0.08) > abs(right - 0.08)


def test_cross_sectional_scores_are_per_bar(panel):
    pred = np.arange(30.0).reshape(5, 6)
    z = cross_sectional_scores(pred)
    assert np.allclose(z.mean(axis=1), 0.0, atol=1e-12)
    # every bar is standardised independently, so a constant row offset cancels
    assert np.allclose(z, cross_sectional_scores(pred + np.arange(5)[:, None] * 100.0))


def test_smoothing_and_holding_cut_turnover():
    rng = np.random.default_rng(0)
    scores = rng.standard_normal((400, 20))
    y = rng.standard_normal((400, 20)) * 0.01
    raw = build_book(scores, 0.2)
    sm = build_book(smooth_scores(scores, 5.0), 0.2)
    held = hold_between_rebalances(raw, 5)
    _, s_raw = book_pnl(raw, y, 0.0015)
    _, s_sm = book_pnl(sm, y, 0.0015)
    _, s_held = book_pnl(held, y, 0.0015)
    assert s_sm["turnover_per_bar"] < s_raw["turnover_per_bar"]
    assert s_held["turnover_per_bar"] < s_raw["turnover_per_bar"]


def test_smoothing_only_looks_backward():
    s = np.zeros((10, 3))
    s[5] = 1.0
    out = smooth_scores(s, 3.0)
    assert np.all(out[:5] == 0.0)          # a spike at bar 5 cannot affect bars 0-4
    assert out[5].max() > 0 and out[6].max() > 0
