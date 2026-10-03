import pytest

from tfm_edge.risk.brackets import barrier_win_probability, breached, make_bracket
from tfm_edge.risk.limits import BLOCK, HALT, RiskConfig, check_account, check_plan, has_halt

CFG = RiskConfig(max_capital=10_000)


def test_daily_loss_limit_halts():
    assert check_account(9_850, 10_000, 10_000, CFG) == []                       # -1.5%
    v = check_account(9_790, 10_000, 10_000, CFG)                                # -2.1%
    assert [x.rule for x in v] == ["daily_loss_limit", "max_drawdown"][:1] and has_halt(v)


def test_drawdown_halts_independently_of_the_day():
    v = check_account(8_900, 8_900, 10_000, CFG)                                  # flat day, -11% from peak
    assert [x.rule for x in v] == ["max_drawdown"] and v[0].severity == HALT


def test_account_checks_tolerate_missing_history():
    assert check_account(10_000, None, None, CFG) == []


def _plan(qty, prices=None, cur=None, capital=10_000, cfg=CFG):
    prices = prices or {s: 100.0 for s in qty}
    return check_plan(qty, cur or {}, prices, capital, cfg)


def test_a_clean_plan_passes():
    q = {"A": 5, "B": 5, "C": -5, "D": -5}                                        # 5% names, neutral
    assert _plan(q, cfg=RiskConfig(max_capital=10_000, max_turnover_per_day=5)) == []


def test_exposure_and_name_limits_block():
    rules = lambda v: {x.rule for x in v}
    assert "max_gross_exposure" in rules(_plan({"A": 60, "B": -60}))              # gross 1.2
    assert "max_net_exposure" in rules(_plan({"A": 40, "B": -10}))                # net +0.30
    assert "max_name_weight" in rules(_plan({"A": 10, "B": -10}))                 # 10% names
    assert all(v.severity == BLOCK for v in _plan({"A": 60, "B": -60}))


def test_capital_above_the_ceiling_blocks():
    v = _plan({"A": 1, "B": -1}, capital=20_000)
    assert "max_capital" in {x.rule for x in v}


def test_turnover_sanity_catches_bad_data():
    cur = {f"S{i}": 5 for i in range(10)}
    flip = {f"S{i}": -5 for i in range(10)}                                       # reverse every position
    prices = {s: 100.0 for s in cur}
    tight = RiskConfig(max_capital=10_000, max_turnover_per_day=0.5)
    assert "max_turnover_per_day" in {x.rule for x in check_plan(flip, cur, prices, 10_000, tight)}
    # and the same trade at exactly the limit is allowed: the bound is inclusive
    edge = RiskConfig(max_capital=10_000, max_turnover_per_day=1.0)
    assert "max_turnover_per_day" not in {x.rule for x in check_plan(flip, cur, prices, 10_000, edge)}


def test_missing_or_tiny_prices_block():
    assert "price_missing" in {x.rule for x in check_plan({"A": 1}, {}, {}, 10_000, CFG)}
    assert "min_price" in {x.rule for x in check_plan({"A": 100}, {}, {"A": 1.5}, 10_000, CFG)}


def test_order_count_and_size_caps():
    many = {f"S{i}": 1 for i in range(100)}
    prices = {s: 10.0 for s in many}
    cfg = RiskConfig(max_capital=1e6, max_orders_per_day=50, max_gross_exposure=5, max_net_exposure=5,
                     max_turnover_per_day=50)
    assert "max_orders_per_day" in {x.rule for x in check_plan(many, {}, prices, 1e6, cfg)}
    big = RiskConfig(max_capital=10_000, max_order_notional=200, max_name_weight=0.5, max_gross_exposure=5,
                     max_net_exposure=5, max_turnover_per_day=50)
    assert "max_order_notional" in {x.rule for x in check_plan({"A": 5}, {}, {"A": 100.0}, 10_000, big)}


# ---- brackets ------------------------------------------------------------------------
def test_bracket_geometry_is_symmetric_around_entry():
    b = make_bracket(100.0, "long", 0.02, CFG)
    assert b.stop == pytest.approx(94.0) and b.target == pytest.approx(106.0)
    s = make_bracket(100.0, "short", 0.02, CFG)
    assert s.stop == pytest.approx(106.0) and s.target == pytest.approx(94.0)


def test_win_rate_is_set_by_geometry_not_by_edge():
    """The point of the barrier note: a 3:1 stop-to-target ratio 'wins' 75% of the time on
    PURE NOISE. Simulate a driftless walk and confirm the formula."""
    import numpy as np
    rng = np.random.default_rng(0)
    sl, tp, wins, n = 3.0, 1.0, 0, 3000
    for _ in range(n):
        x = 0.0
        while -sl < x < tp:
            x += rng.choice((-0.1, 0.1))
        wins += x >= tp
    assert abs(wins / n - barrier_win_probability(sl, tp)) < 0.03
    assert barrier_win_probability(3, 1) == pytest.approx(0.75)


def test_breach_assumes_the_stop_when_both_could_have_hit():
    b = make_bracket(100.0, "long", 0.02, CFG)
    assert breached(b, low=93.0, high=107.0) == "stop"
    assert breached(b, low=99.0, high=107.0) == "target"
    assert breached(b, low=99.0, high=101.0) is None
    s = make_bracket(100.0, "short", 0.02, CFG)
    assert breached(s, low=93.0, high=99.0) == "target"
    assert breached(s, low=99.0, high=107.0) == "stop"


def test_bracket_rejects_nonsense_inputs():
    with pytest.raises(ValueError):
        make_bracket(0.0, "long", 0.02, CFG)
    with pytest.raises(ValueError):
        make_bracket(100.0, "flat", 0.02, CFG)
