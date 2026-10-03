import numpy as np

from tfm_edge.analysis.feasibility import (
    evaluate, min_track_record_years, naive_break_even_hit_rate, sharpe_per_bar,
    signal_size_given_selected, trade_fraction,
)


def test_selection_identities():
    assert np.isclose(signal_size_given_selected(0.0), np.sqrt(2 / np.pi))
    assert np.isclose(trade_fraction(0.0), 1.0)
    # E[|z| | |z|>tau] rises without bound; that is why selection concentrates the edge
    assert signal_size_given_selected(2.0) > signal_size_given_selected(1.0) > signal_size_given_selected(0.0)
    assert trade_fraction(2.0) < 0.05


def test_break_even_matches_harness_formula():
    """p* = 0.5 + 0.6267 k must agree with metrics.break_even_hit_rate on the same inputs."""
    from tfm_edge.analysis.metrics import break_even_hit_rate
    sigma, cost = 0.00395, 0.0015          # BTC 1h: 39.5 bps vol, 15 bps round trip
    y = np.random.default_rng(0).standard_normal(200000) * sigma
    k = cost / sigma
    assert abs(naive_break_even_hit_rate(k) - break_even_hit_rate(y, cost)) < 0.002


def test_cheap_setup_needs_far_less_edge():
    btc = evaluate("btc_1h", vol_annual=0.37, bars_per_year=8760, cost_rt_bps=15.0, ic=0.03)
    es = evaluate("es_1d", vol_annual=0.16, bars_per_year=252, cost_rt_bps=0.9, ic=0.03)
    assert btc.k > 20 * es.k
    assert btc.naive_break_even > 0.70 and es.naive_break_even < 0.52
    assert es.sharpe_at_ic > 0 > btc.sharpe_at_ic


def test_breadth_multiplies_sharpe_by_sqrt():
    one = evaluate("x", vol_annual=0.25, bars_per_year=252, cost_rt_bps=3.0, ic=0.03, breadth=1.0)
    many = evaluate("x", vol_annual=0.25, bars_per_year=252, cost_rt_bps=3.0, ic=0.03, breadth=16.0)
    assert 3.5 < many.sharpe_at_ic / one.sharpe_at_ic < 4.5
    assert many.years_to_prove < one.years_to_prove


def test_zero_ic_is_never_profitable():
    assert np.all(sharpe_per_bar(0.0, 0.05, np.linspace(0, 4, 50)) <= 0)


def test_track_record_length_shrinks_with_sharpe():
    assert min_track_record_years(2.0) < min_track_record_years(0.5) < min_track_record_years(0.2)
    assert not np.isfinite(min_track_record_years(-0.1))
