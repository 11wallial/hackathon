import numpy as np
import pytest

from tfm_edge.analysis import divergence as dv
from tfm_edge.execution import engine

from .bot_harness import Sim, slice_panel

RT = 3e-4


def test_shadow_return_arithmetic_on_a_hand_computed_case():
    """One long, one short, two sessions. Every number checked by hand."""
    from tfm_edge.data.panel import Panel
    t = np.array(["2026-03-02", "2026-03-03", "2026-03-04"], dtype="datetime64[ns]")
    op = np.array([[100., 50.], [101., 49.], [103., 48.]])
    cl = np.array([[100., 50.], [102., 48.], [104., 49.]])
    p = Panel(open_time=t, close_time=t, log_close=np.log(cl), log_open=np.log(op), symbols=["L", "S"], bar="1d")
    ideal = {"2026-03-03": {"L": 0.5, "S": -0.5}, "2026-03-04": {"L": 0.5, "S": -0.5}}
    r = dv.shadow_returns(ideal, p, RT, ["2026-03-03", "2026-03-04"])
    # 03-04: gap on the held book, then open-to-close on the (unchanged) book, no turnover
    gap = 0.5 * (103 / 102 - 1) - 0.5 * (48 / 48 - 1)
    intraday = 0.5 * (104 / 103 - 1) - 0.5 * (49 / 48 - 1)
    assert r["2026-03-04"] == pytest.approx(gap + intraday)


def test_turnover_is_charged_at_half_a_round_trip_per_unit():
    from tfm_edge.data.panel import Panel
    t = np.array(["2026-03-02", "2026-03-03", "2026-03-04"], dtype="datetime64[ns]")
    flat = np.full((3, 1), 100.0)
    p = Panel(open_time=t, close_time=t, log_close=np.log(flat), log_open=np.log(flat), symbols=["A"], bar="1d")
    ideal = {"2026-03-03": {"A": 0.5}, "2026-03-04": {"A": -0.5}}                 # a full reversal
    r = dv.shadow_returns(ideal, p, RT, ["2026-03-03", "2026-03-04"])
    assert r["2026-03-04"] == pytest.approx(-1.0 * RT / 2.0)                       # |dw| = 1.0


def test_a_day_without_a_plan_holds_the_previous_book():
    from tfm_edge.data.panel import Panel
    t = np.array(["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"], dtype="datetime64[ns]")
    cl = np.array([[100.], [100.], [110.], [121.]])
    p = Panel(open_time=t, close_time=t, log_close=np.log(cl), log_open=np.log(cl), symbols=["A"], bar="1d")
    r = dv.shadow_returns({"2026-03-03": {"A": 1.0}}, p, 0.0, ["2026-03-04", "2026-03-05"])
    assert r["2026-03-04"] == pytest.approx(0.10) and r["2026-03-05"] == pytest.approx(0.10)


def test_paper_account_tracks_its_own_shadow_closely(tmp_path):
    """Same prices, same cost model: the only gaps are whole-share rounding and bracket hits.
    A large gap here would mean the paper broker and the backtest disagree about the world."""
    s = Sim(tmp_path)
    for _ in range(20):
        s.day_cycle()
    s.at(s.evening()); engine.reconcile(s.ctx)
    out = dv.compute(s.ctx.store, slice_panel(s.panel, s.k), capital=s.cfg.capital,
                     round_trip_frac=s.ctx.run.costs.round_trip_frac())
    assert out["n"] >= 15
    assert out["corr"] > 0.9
    assert abs(out["mean_gap_bps"]) < 5.0, out["mean_gap_bps"]


def test_a_broker_that_charges_more_than_the_model_opens_a_gap(tmp_path):
    from tfm_edge.config import CostModel
    from tfm_edge.execution.broker import PaperBroker
    from tfm_edge.execution.store import Store
    st = Store(":memory:")
    pricey = PaperBroker(st, 100_000.0, CostModel(0.2, 6.0, 4.0))                  # ~10x the modelled slippage
    s = Sim(tmp_path, broker=pricey)
    s.ctx.store = st
    pricey._now = lambda: s.t
    for _ in range(20):
        s.day_cycle()
    s.at(s.evening()); engine.reconcile(s.ctx)
    out = dv.compute(s.ctx.store, slice_panel(s.panel, s.k), capital=s.cfg.capital,
                     round_trip_frac=s.ctx.run.costs.round_trip_frac())
    assert out["mean_gap_bps"] < -0.5                                              # shortfall is visible and negative
    assert out["z_gap"] < -2.0


def test_report_renders_with_and_without_a_backtest(tmp_path):
    s = Sim(tmp_path)
    for _ in range(8):
        s.day_cycle()
    s.at(s.evening()); engine.reconcile(s.ctx)
    res = dv.compute(s.ctx.store, slice_panel(s.panel, s.k), capital=s.cfg.capital,
                     round_trip_frac=s.ctx.run.costs.round_trip_frac())
    dv.write_daily_report(res, tmp_path / "r.md", mode="paper", name="t")
    assert "No real-data Phase 1 report" in (tmp_path / "r.md").read_text()
    res["expectation"] = {"report": "x", "verdict": "PROCEED", "mean_bps": 4.0, "sd_bps": 50.0}
    dv.write_daily_report(res, tmp_path / "r2.md", mode="paper", name="t")
    assert "Backtest expectation" in (tmp_path / "r2.md").read_text()


def test_no_history_is_reported_not_crashed(tmp_path):
    s = Sim(tmp_path)
    out = dv.compute(s.ctx.store, slice_panel(s.panel, s.k), capital=1e5, round_trip_frac=RT)
    assert out["n"] == 0 and "need at least" in out["note"]
