"""The decision function is pure and must match the backtest's book construction."""
import numpy as np
import pytest

from tfm_edge.config import CostModel
from tfm_edge.decision.book import BookConfig, decide
from tfm_edge.features.cross_section import cross_sectional_weights

COSTS = CostModel(0.2, 0.8, 0.5)
LOOSE = dict(max_name_weight=1.0, min_trade_weight=0.0)


def _scores(n=30, seed=0):
    rng = np.random.default_rng(seed)
    return {f"S{i:02d}": float(v) for i, v in enumerate(rng.standard_normal(n))}


def test_matches_backtest_construction_exactly():
    """With every name eligible and nothing constraining, live == backtest."""
    for n, tf in [(30, 0.2), (50, 0.1), (11, 0.3), (7, 0.5)]:
        sc = _scores(n, seed=n)
        d = decide(sc, {}, BookConfig(top_fraction=tf, gross=1.0, **LOOSE), COSTS)
        names = sorted(sc)
        ref = cross_sectional_weights(np.array([sc[s] for s in names]), tf, 1.0)
        got = np.array([d.target.get(s, 0.0) for s in names])
        assert np.allclose(got, ref), (n, tf)


def test_dollar_neutral_and_gross():
    d = decide(_scores(), {}, BookConfig(**LOOSE), COSTS)
    assert d.net == pytest.approx(0.0, abs=1e-12)
    assert d.gross == pytest.approx(1.0)
    assert d.n_long == d.n_short == 6


def test_deterministic_and_input_order_independent():
    sc = _scores()
    a = decide(sc, {}, BookConfig(**LOOSE), COSTS)
    b = decide(dict(reversed(list(sc.items()))), {}, BookConfig(**LOOSE), COSTS)
    assert a.target == b.target and a.sides == b.sides


def test_ties_break_on_symbol_not_on_chance():
    sc = {f"S{i:02d}": 0.0 for i in range(20)}
    runs = {tuple(sorted(decide(sc, {}, BookConfig(**LOOSE), COSTS).target.items())) for _ in range(5)}
    assert len(runs) == 1


def test_name_cap_binds_and_is_reported():
    d = decide(_scores(), {}, BookConfig(max_name_weight=0.02, min_trade_weight=0.0), COSTS)
    assert max(abs(w) for w in d.target.values()) == pytest.approx(0.02)
    assert d.gross < 1.0
    assert any("name cap" in n for n in d.notes)


def test_cadence_holds_between_rebalances():
    sc = _scores()
    held = {"S01": 0.1, "S02": -0.1}
    d = decide(sc, held, BookConfig(rebalance_every=5, **LOOSE), COSTS, sessions_since_rebalance=2)
    assert not d.rebalanced and d.target == held and d.turnover == 0.0
    d = decide(sc, held, BookConfig(rebalance_every=5, **LOOSE), COSTS, sessions_since_rebalance=5)
    assert d.rebalanced and d.target != held


def test_unscorable_holdings_are_exited_even_while_holding():
    sc = _scores()
    held = {"S01": 0.1, "GONE": 0.1}
    d = decide(sc, held, BookConfig(rebalance_every=5, **LOOSE), COSTS, sessions_since_rebalance=1)
    assert "GONE" not in d.target and "S01" in d.target
    assert any("forced exit" in n for n in d.notes)


def test_no_trade_band_suppresses_small_changes_but_not_exits():
    sc = {f"S{i:02d}": float(i) for i in range(20)}
    base = decide(sc, {}, BookConfig(**LOOSE), COSTS).target
    drifted = {s: w * 0.9995 for s, w in base.items()}          # 0.05% off target
    d = decide(sc, drifted, BookConfig(max_name_weight=1.0, min_trade_weight=0.002), COSTS)
    assert d.names_changed == 0 and d.turnover == 0.0
    gone = dict(drifted); gone["ZOMBIE"] = 0.0005                # tiny but unscorable
    d = decide(sc, gone, BookConfig(max_name_weight=1.0, min_trade_weight=0.002), COSTS)
    assert "ZOMBIE" not in d.target


def test_unshortable_names_are_skipped_and_next_ranked_is_used():
    sc = {f"S{i:02d}": float(i) for i in range(20)}              # S00..S03 are the shorts
    d = decide(sc, {}, BookConfig(**LOOSE), COSTS, can_short=set(sc) - {"S00", "S01"})
    shorts = sorted(s for s, w in d.target.items() if w < 0)
    assert "S00" not in shorts and "S01" not in shorts and len(shorts) == 4
    assert any("eligibility" in n for n in d.notes) is False      # still filled the side


def test_shrunk_side_is_reported_and_still_sized_to_its_half():
    sc = {f"S{i:02d}": float(i) for i in range(20)}
    d = decide(sc, {}, BookConfig(**LOOSE), COSTS, can_short={"S00", "S01"})
    assert d.n_short == 2 and any("eligibility shrank" in n for n in d.notes)
    assert sum(w for w in d.target.values() if w < 0) == pytest.approx(-0.5)


def test_net_edge_filter_applies_to_new_entries_only():
    sc = {f"S{i:02d}": float(i) for i in range(20)}
    fc = {s: 0.0 for s in sc}                                    # model says "0 bps" everywhere
    cfg = BookConfig(net_edge_threshold_bps=0.0, **LOOSE)
    d = decide(sc, {}, cfg, COSTS, forecast_bps=fc)
    assert d.target == {} and any("net-edge filter" in n for n in d.notes)
    held = {"S19": 0.1, "S00": -0.1}                             # existing positions are not re-gated
    d = decide(sc, held, cfg, COSTS, forecast_bps=fc)
    assert "S19" in d.target and "S00" in d.target


def test_empty_and_tiny_universes_do_not_crash():
    assert decide({}, {}, BookConfig(), COSTS).target == {}
    assert decide({"A": 1.0}, {}, BookConfig(**LOOSE), COSTS).target == {}
    d = decide({"A": 1.0, "B": -1.0}, {}, BookConfig(**LOOSE), COSTS)
    assert d.target["A"] > 0 > d.target["B"]


def test_nonfinite_scores_are_not_tradable():
    sc = _scores(); sc["S00"] = float("nan"); sc["S01"] = float("inf")
    d = decide(sc, {"S00": 0.1}, BookConfig(**LOOSE), COSTS)
    assert "S00" not in d.target and "S01" not in d.target


def test_decision_does_not_mutate_its_inputs():
    sc, cur = _scores(), {"S03": 0.05}
    sc0, cur0 = dict(sc), dict(cur)
    decide(sc, cur, BookConfig(**LOOSE), COSTS)
    assert sc == sc0 and cur == cur0
