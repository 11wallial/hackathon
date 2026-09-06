"""Hard constraint 2. These tests prove the harness *would* catch a leak, which is
the only kind of evidence that it currently has none."""
import numpy as np
import pytest

from tfm_edge.analysis.walkforward import Fold, assert_no_overlap, make_folds
from tfm_edge.config import WalkForwardConfig
from tfm_edge.features.samples import build_samples, context_window


def test_targets_start_after_decision(rw_bars):
    s = build_samples(rw_bars, horizon=3, context_len=64)
    lc = np.log(rw_bars["close"].to_numpy())
    lo = np.log(rw_bars["open"].to_numpy())
    i = 100
    t = s.t[i]
    assert np.isclose(s.y_cc[i], lc[t + 3] - lc[t])
    assert np.isclose(s.y_oo[i], lo[t + 4] - lo[t + 1])
    # decision is knowable at close_time[t]; first fill is open_time[t+1], never earlier
    assert s.executes_at[i] >= s.decision_at[i]
    assert rw_bars["open_time"].to_numpy()[t] < s.decision_at[i]


def test_context_ends_at_decision_bar(rw_bars):
    lc = np.log(rw_bars["close"].to_numpy())
    w = context_window(lc, 500, 128)
    assert len(w) == 128 and w[-1] == lc[500] and w[0] == lc[373]


def test_cheating_forecaster_is_exposed(rw_bars):
    """A forecaster that peeks at close[t+1] must score ~100%, proving the hit-rate
    metric is aligned with the label and would expose a leak."""
    s = build_samples(rw_bars, horizon=1, context_len=64)
    lc = np.log(rw_bars["close"].to_numpy())
    peek = lc[s.t + 1] - lc[s.t]          # this is the leak
    hits = np.mean(np.sign(peek) == np.sign(s.y_cc))
    assert hits > 0.99
    honest = lc[s.t] - lc[s.t - 1]        # last return, legitimately knowable
    assert abs(np.mean(np.sign(honest) == np.sign(s.y_cc)) - 0.5) < 0.03


def test_purge_and_embargo(rw_bars):
    s = build_samples(rw_bars, horizon=4, context_len=64)
    cfg = WalkForwardConfig(n_splits=4, embargo_bars=10, min_train_bars=1000)
    folds = make_folds(s, cfg)
    for f in folds:
        assert_no_overlap(s, f)
        t0 = s.t[f.test_sample_idx[0]]
        # last training return index is t0 - H - embargo; its label ends at t0 - embargo < t0
        assert f.train_return_end - 1 == t0 - 4 - 10
    # forward chaining: later folds never test before earlier ones
    starts = [s.t[f.test_sample_idx[0]] for f in folds]
    assert starts == sorted(starts)


def test_overlap_assertion_fires(rw_bars):
    s = build_samples(rw_bars, horizon=4, context_len=64)
    t0 = 2000
    idx = np.where(s.t >= t0)[0]
    bad = Fold(0, train_return_end=t0, test_sample_idx=idx)   # no purge: label of u=t0-1 ends at t0+3
    with pytest.raises(AssertionError):
        assert_no_overlap(s, bad)


def test_gapped_bars_rejected():
    from tfm_edge.data.bars import validate_bars
    from tfm_edge.data.synthetic import generate
    df = generate("random_walk", 200, seed=1)
    df = df.drop(index=50)
    with pytest.raises(ValueError):
        validate_bars(df, "1h")
