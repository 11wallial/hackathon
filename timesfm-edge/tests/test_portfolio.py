import numpy as np

from tfm_edge.analysis.deflated_sharpe import deflated_sharpe, expected_max_sharpe, probabilistic_sharpe
from tfm_edge.analysis.portfolio import backtest, expanding_standardise, positions, sweep


def test_expanding_standardise_uses_only_the_past():
    rng = np.random.default_rng(0)
    p = rng.standard_normal(500)
    z = expanding_standardise(p, min_obs=50)
    # changing a later value must not move an earlier z-score
    p2 = p.copy()
    p2[400] += 100.0
    z2 = expanding_standardise(p2, min_obs=50)
    assert np.array_equal(z[:400], z2[:400])
    assert z[400] != z2[400]
    assert np.all(z[:50] == 0)


def test_turnover_costs_reward_persistence():
    y = np.zeros(1000)
    flip = np.tile([2.0, -2.0], 500)          # flips every bar
    hold = np.concatenate([np.full(500, 2.0), np.full(500, -2.0)])
    rf, _ = backtest(flip, y, 0.0015, 0.0, 252)
    rh, _ = backtest(hold, y, 0.0015, 0.0, 252)
    assert rf.turnover_per_bar > 1.9 and rh.turnover_per_bar < 0.01
    assert rf.mean_cost_bps > 100 * rh.mean_cost_bps


def test_full_reversal_costs_exactly_one_round_trip():
    """Cost is charged per unit of |dw| at half a round trip, so a -1 -> +1 reversal
    costs exactly one round trip and an entry from flat costs half of one."""
    r, _ = backtest(np.array([2.0, -2.0, 2.0, -2.0]), np.zeros(4), 0.0015, 0.0, 252, sizing="binary")
    # one entry from flat (|dw|=1) plus three full reversals (|dw|=2) over four bars
    assert np.isclose(r.turnover_per_bar, 7 / 4)
    assert np.isclose(r.mean_cost_bps, 1e4 * 0.0015 * (7 / 4) / 2)
    held, _ = backtest(np.full(4, 2.0), np.zeros(4), 0.0015, 0.0, 252, sizing="binary")
    assert np.isclose(held.mean_cost_bps, 1e4 * 0.0015 / 2 / 4)   # one entry, never traded again


def test_selection_band_produces_flat():
    z = np.array([0.1, -0.2, 3.0, -3.0])
    w = positions(z, tau=1.0, sizing="binary")
    assert list(w) == [0.0, 0.0, 1.0, -1.0]


def test_sweep_finds_edge_and_rejects_noise():
    rng = np.random.default_rng(1)
    n, sig = 12000, 0.0113
    z = rng.standard_normal(n)
    y = sig * (0.06 * z + np.sqrt(1 - 0.06 ** 2) * rng.standard_normal(n))
    good = sweep(z, y, 1.25e-4, 252)
    assert good.dsr_passes and good.best["sharpe_annual"] > 0.4
    noise = sweep(z, sig * rng.standard_normal(n), 1.25e-4, 252)
    assert not noise.dsr_passes


def test_same_edge_fails_when_costs_are_high():
    """The identical signal on an expensive, high-frequency instrument does not pass.
    This is the whole finding: setup decides the verdict, not the model."""
    rng = np.random.default_rng(1)
    n = 12000
    z = rng.standard_normal(n)
    cheap = 0.0113 * (0.06 * z + np.sqrt(1 - 0.06 ** 2) * rng.standard_normal(n))
    assert sweep(z, cheap, 1.25e-4, 252).dsr_passes
    dear = 0.00395 * (0.06 * z + np.sqrt(1 - 0.06 ** 2) * rng.standard_normal(n))
    assert not sweep(z, dear, 15e-4, 8760).dsr_passes


def test_sweep_never_selects_a_cell_that_does_not_trade():
    rng = np.random.default_rng(2)
    y = rng.standard_normal(500) * 0.01
    r = sweep(np.zeros(500), y, 1e-4, 252)      # signal never clears any threshold
    assert r.best["trade_fraction"] == 0.0 or r.best["turnover_per_bar"] > 0


def test_expected_max_null_sharpe_grows_with_trials():
    a, b = expected_max_sharpe(10, 0.01), expected_max_sharpe(1000, 0.01)
    assert 0 < a < b
    assert b / a < 2.5          # grows like sqrt(log N), so 100x the trials is not 100x the bar


def test_deflation_punishes_many_trials():
    rng = np.random.default_rng(3)
    r = rng.standard_normal(2000) * 0.01 + 0.0005
    trial_sharpes = rng.standard_normal(500) * 0.03      # variants must actually disagree
    few = deflated_sharpe(r, 1, obs_per_year=252)
    many = deflated_sharpe(r, 500, trial_sharpes, obs_per_year=252)
    assert few.deflated_sharpe > many.deflated_sharpe
    assert many.expected_max_null_sharpe > 0
    assert np.isfinite(few.psr_vs_zero)


def test_identical_trials_carry_no_selection_penalty():
    """If every variant scored the same there was nothing to select between, so the
    best-of-N benchmark is zero however many were run."""
    assert expected_max_sharpe(1000, 0.0) == 0.0


def test_probabilistic_sharpe_is_a_probability():
    rng = np.random.default_rng(4)
    p = probabilistic_sharpe(rng.standard_normal(1000) * 0.01 + 0.001)
    assert 0.0 <= p <= 1.0
