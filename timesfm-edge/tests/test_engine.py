"""The engine, replayed against a synthetic market. Time and bars are injected."""
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from .bot_harness import Sim
from tfm_edge.execution import engine
from tfm_edge.execution.broker import LiveNotCleared, PaperBroker
from tfm_edge.execution.store import Store


@pytest.fixture
def sim(tmp_path):
    return Sim(tmp_path)


def run_days(sim, n):
    out = []
    for _ in range(n):
        out.append(sim.day_cycle())
    return out


# ---- a normal run ---------------------------------------------------------------------------
def test_two_weeks_of_paper_trading_keeps_every_invariant(sim):
    cfg = sim.cfg
    for _ in range(14):
        sim.day_cycle()
        acct = sim.ctx.broker.get_account()
        pos = sim.ctx.broker.get_positions()
        # accounting identity: the paper ledger always balances
        assert acct.equity == pytest.approx(acct.cash + sum(p.market_value for p in pos.values()))
        gross = sum(abs(p.market_value) for p in pos.values()) / cfg.capital
        net = sum(p.market_value for p in pos.values()) / cfg.capital
        assert gross <= cfg.risk.max_gross_exposure + 0.05          # +slack for a day of price drift
        assert abs(net) <= 0.25
        assert all(abs(p.market_value) / cfg.capital <= cfg.risk.max_name_weight + 0.03 for p in pos.values())
    kinds = {e["kind"] for e in sim.ctx.store.events(500)}
    assert {"plan", "reconcile", "execute", "paper_fill"} <= kinds
    assert len(sim.ctx.store.equity_by_session()) >= 14
    assert len(sim.ctx.store.ideal_weights()) >= 14                  # the shadow book for the divergence report


def test_book_is_built_and_roughly_dollar_neutral_after_the_first_fill(sim):
    sim.day_cycle(); sim.day_cycle()                                  # plan, execute, then settle at the next evening
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    pos = sim.ctx.broker.get_positions()
    longs = [p for p in pos.values() if p.qty > 0]; shorts = [p for p in pos.values() if p.qty < 0]
    assert len(longs) >= 4 and len(shorts) >= 4
    net = sum(p.market_value for p in pos.values()) / sim.cfg.capital
    assert abs(net) < 0.15


def test_planning_is_deterministic(tmp_path):
    a, b = Sim(tmp_path / "a"), Sim(tmp_path / "b")
    for s in (a, b):
        s.at(s.evening())
    pa, pb = engine.plan(a.ctx), engine.plan(b.ctx)
    assert pa["payload"]["fingerprint"] == pb["payload"]["fingerprint"]
    assert pa["payload"]["orders"] == pb["payload"]["orders"]


def test_planning_twice_for_the_same_session_is_idempotent(sim):
    sim.at(sim.evening())
    p1 = engine.plan(sim.ctx); p2 = engine.plan(sim.ctx)
    assert p1["id"] == p2["id"]


# ---- the plan/approve/execute split ----------------------------------------------------------
def test_approval_is_required_when_configured(tmp_path):
    s = Sim(tmp_path, require_approval=True)
    s.at(s.evening())
    pl = engine.plan(s.ctx)
    assert pl["status"] == "pending" and pl["payload"]["orders"]
    s.at(s.morning())
    assert engine.execute(s.ctx)["status"] == "no_approved_plan"       # nothing runs unapproved
    engine.approve(s.ctx, pl["id"])
    res = engine.execute(s.ctx)
    assert res["status"] == "executed" and res["submitted"] == len(pl["payload"]["orders"])


def test_a_rejected_plan_never_executes(tmp_path):
    s = Sim(tmp_path, require_approval=True)
    s.at(s.evening()); pl = engine.plan(s.ctx)
    engine.reject(s.ctx, pl["id"])
    s.at(s.morning())
    assert engine.execute(s.ctx)["status"] == "no_approved_plan"
    with pytest.raises(ValueError):
        engine.approve(s.ctx, pl["id"])


def test_execute_twice_does_not_double_the_orders(sim):
    sim.at(sim.evening()); engine.plan(sim.ctx)
    sim.at(sim.morning())
    first = engine.execute(sim.ctx)
    n_orders = len(sim.ctx.store.q("SELECT * FROM orders"))
    assert engine.execute(sim.ctx)["status"] == "no_approved_plan"
    assert len(sim.ctx.store.q("SELECT * FROM orders")) == n_orders and first["status"] == "executed"


def test_a_plan_is_never_executed_late(sim):
    sim.at(sim.evening()); pl = engine.plan(sim.ctx)
    sim.at(sim.morning() + timedelta(hours=1, minutes=30))             # 10:30 ET, after the open
    res = engine.execute(sim.ctx)
    assert res["status"] == "expired"
    assert sim.ctx.store.plan(pl["id"])["status"] == "expired"
    assert sim.ctx.store.q("SELECT * FROM orders") == []


def test_positions_changing_between_plan_and_execute_blocks_the_run(sim):
    sim.day_cycle(); sim.day_cycle()
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    pl = engine.plan(sim.ctx)
    assert pl["status"] in ("approved", "noop")
    if pl["status"] == "approved":
        sim.ctx.broker.submit_order(next(iter(sim.panel.symbols)), "buy", 3, tif="opg", client_id="manual-1")
        sim.ctx.broker.settle_session("x", sim.ctx.calendar.open_utc(sim.day(sim.k) + timedelta(days=1)),
                                      {sim.panel.symbols[0]: {"open": 100, "high": 101, "low": 99, "close": 100}})
        sim.at(sim.morning())
        res = engine.execute(sim.ctx)
        assert res["status"] == "blocked" and "positions changed" in res["reason"]


# ---- data problems must stop the bot, not feed it ---------------------------------------------
def test_stale_data_blocks_planning(sim):
    sim.at(sim.evening(sim.k + 3))                                      # three days later, no new bars published
    pl = engine.plan(sim.ctx)
    assert pl["status"] == "blocked" and "stale data" in pl["note"]
    assert sim.ctx.store.q("SELECT * FROM orders") == []


def test_thin_coverage_blocks_planning(sim):
    sim.panel.log_close[sim.k, :20] = np.nan                             # 20 of 30 names missing today
    sim.panel.log_open[sim.k, :20] = np.nan
    sim.at(sim.evening())
    pl = engine.plan(sim.ctx)
    assert pl["status"] == "blocked" and "coverage" in pl["note"]


def test_a_failing_data_source_blocks_planning(sim):
    def boom():
        raise ConnectionError("no route to host")
    sim.ctx.load_panel = boom
    sim.at(sim.evening())
    pl = engine.plan(sim.ctx)
    assert pl["status"] == "blocked" and "could not load bars" in pl["note"]


# ---- kill switch ------------------------------------------------------------------------------
def test_the_kill_file_blocks_planning_and_execution(sim):
    sim.day_cycle()
    Path(sim.cfg.kill_file).parent.mkdir(parents=True, exist_ok=True)
    Path(sim.cfg.kill_file).write_text("manual halt")
    sim.at(sim.evening()); pl = engine.plan(sim.ctx)
    assert pl["status"] == "blocked" and "manual halt" in pl["note"]
    assert engine.kill_state(sim.ctx)["source"] == "file"


def test_halt_in_the_ledger_blocks_execution_of_an_already_approved_plan(sim):
    sim.at(sim.evening()); pl = engine.plan(sim.ctx)
    assert pl["status"] == "approved"
    engine.kill(sim.ctx, "operator pressed the button", by="test")
    sim.at(sim.morning())
    res = engine.execute(sim.ctx)
    assert res["status"] == "blocked" and sim.ctx.store.q("SELECT * FROM orders") == []


def test_kill_cancels_entry_orders_but_leaves_protective_exits(sim):
    for _ in range(3):
        sim.day_cycle()
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    assert sim.ctx.store.brackets(), "positions should have brackets by now"
    sim.ctx.broker.submit_order(sim.panel.symbols[0], "buy", 1, tif="opg", client_id="tfm-e-test")
    out = engine.kill(sim.ctx, "test", by="test")
    working = sim.ctx.broker.get_open_orders()
    assert out["cancelled"] >= 1 and working and all(o.kind == "oco" for o in working)


def test_flatten_closes_everything(sim):
    for _ in range(3):
        sim.day_cycle()
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    assert sim.ctx.broker.get_positions()
    engine.kill(sim.ctx, "test", flatten=True, by="test")
    assert sim.ctx.broker.get_positions() == {} and sim.ctx.broker.get_open_orders() == []


def test_resume_requires_the_typed_word_and_a_removed_kill_file(sim):
    engine.kill(sim.ctx, "test", by="test")
    with pytest.raises(ValueError):
        engine.resume(sim.ctx, "yes")
    Path(sim.cfg.kill_file).parent.mkdir(parents=True, exist_ok=True)
    Path(sim.cfg.kill_file).write_text("x")
    with pytest.raises(RuntimeError, match="Remove it yourself"):
        engine.resume(sim.ctx, "RESUME")
    Path(sim.cfg.kill_file).unlink()
    engine.resume(sim.ctx, "RESUME")
    assert engine.kill_state(sim.ctx) is None


def test_daily_loss_limit_halts_the_bot(sim):
    for _ in range(3):
        sim.day_cycle()
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    held = sim.ctx.broker.get_positions()
    assert held
    # an overnight crash in every LONG position, bigger than the 2% daily limit
    marks = sim.ctx.store.get("paper.marks")
    for s, p in held.items():
        marks[s] = marks[s] * (0.75 if p.qty > 0 else 1.25)
    sim.ctx.store.set("paper.marks", marks)
    sim.k += 1
    sim.at(sim.evening()); sim.ctx.store.set("paper.last_session", sim.day(sim.k).isoformat())   # no re-settle
    out = engine.reconcile(sim.ctx)
    assert any("daily_loss_limit" in v for v in out["violations"])
    assert engine.kill_state(sim.ctx)["by"] == "risk"
    assert engine.plan(sim.ctx)["status"] == "blocked"


def test_flatten_on_halt_closes_positions_when_configured(tmp_path):
    s = Sim(tmp_path, risk={"flatten_on_halt": True})
    for _ in range(3):
        s.day_cycle()
    s.at(s.evening()); engine.reconcile(s.ctx)
    marks = s.ctx.store.get("paper.marks")
    for sym, p in s.ctx.broker.get_positions().items():
        marks[sym] *= 0.7 if p.qty > 0 else 1.3
    s.ctx.store.set("paper.marks", marks)
    s.k += 1; s.at(s.evening()); s.ctx.store.set("paper.last_session", s.day(s.k).isoformat())
    engine.reconcile(s.ctx)
    assert s.ctx.broker.get_positions() == {}


# ---- risk checks bite -------------------------------------------------------------------------
def test_risk_limits_block_a_plan_that_would_break_them(tmp_path):
    s = Sim(tmp_path, risk={"max_turnover_per_day": 0.05})              # absurdly tight
    s.at(s.evening())
    pl = engine.plan(s.ctx)
    assert pl["status"] == "blocked" and "max_turnover_per_day" in pl["note"]
    assert s.ctx.store.q("SELECT * FROM orders") == []


def test_capital_is_capped_by_the_risk_ceiling(tmp_path):
    s = Sim(tmp_path, capital=100_000.0)
    s.cfg = s.cfg.__class__(**{**s.cfg.__dict__, "capital": 50_000.0})
    s.ctx.cfg = s.cfg
    s.at(s.evening()); pl = engine.plan(s.ctx)
    assert pl["payload"]["capital"] == 50_000.0
    gross = sum(o["notional"] for o in pl["payload"]["orders"])
    assert gross <= 50_000.0 * 1.2


# ---- the account isn't ours alone ---------------------------------------------------------------
def test_positions_outside_the_universe_are_never_touched(sim):
    broker: PaperBroker = sim.ctx.broker
    store = sim.ctx.store
    store.set("paper.positions", {"MY_HOUSE_FUND": {"qty": 500, "avg": 40.0}})
    sim.at(sim.evening())
    pl = engine.plan(sim.ctx)
    assert all(o["symbol"] != "MY_HOUSE_FUND" for o in pl["payload"]["orders"])
    sim.at(sim.morning()); engine.execute(sim.ctx)
    assert broker.get_positions()["MY_HOUSE_FUND"].qty == 500


def test_unshortable_names_are_not_shorted(tmp_path):
    from tfm_edge.execution.broker import PaperBroker
    from tfm_edge.config import CostModel
    st = Store(":memory:")
    s0 = Sim(tmp_path / "probe")
    s = Sim(tmp_path / "real", broker=PaperBroker(st, 100_000.0, CostModel(0.2, 0.8, 0.5),
                                                 unshortable=set(s0.panel.symbols[:10])))
    s.ctx.store = st
    s.at(s.evening()); pl = engine.plan(s.ctx)
    shorted = {o["symbol"] for o in pl["payload"]["orders"] if o["side"] == "sell"}
    assert shorted and not (shorted & set(s0.panel.symbols[:10]))


# ---- brackets ---------------------------------------------------------------------------------
def test_every_open_position_gets_a_stop_and_a_target(sim):
    for _ in range(3):
        sim.day_cycle()
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    pos, br = sim.ctx.broker.get_positions(), sim.ctx.store.brackets()
    assert pos and set(br) == set(pos)
    for s, b in br.items():
        if b["side"] == "long":
            assert b["stop"] < b["entry"] < b["target"]
        else:
            assert b["target"] < b["entry"] < b["stop"]
    assert {o.symbol for o in sim.ctx.broker.get_open_orders() if o.kind == "oco"} == set(pos)


def test_closed_positions_lose_their_brackets(sim):
    for _ in range(3):
        sim.day_cycle()
    sim.at(sim.evening()); engine.reconcile(sim.ctx)
    engine.kill(sim.ctx, "test", flatten=True, by="test")
    engine.resume(sim.ctx, "RESUME")
    engine.reconcile(sim.ctx)
    assert sim.ctx.store.brackets() == {}


# ---- live clearance ------------------------------------------------------------------------------
def _live_sim(tmp_path, **live):
    return Sim(tmp_path, kind="alpaca_live", require_approval=True, live=live)


def test_live_is_refused_with_no_env_no_gate_no_paper_history(tmp_path):
    s = _live_sim(tmp_path)
    s.at(s.evening()); pl = engine.plan(s.ctx)
    engine.approve(s.ctx, pl["id"])
    s.at(s.morning())
    with pytest.raises(LiveNotCleared) as e:
        engine.execute(s.ctx)
    msg = str(e.value)
    assert "confirm_env" in msg and "gate" in msg and "paper_run" in msg
    assert s.ctx.store.q("SELECT * FROM orders") == []
    assert any(ev["kind"] == "live_refused" for ev in s.ctx.store.events(50))


def test_each_override_clears_only_its_own_check(tmp_path):
    s = _live_sim(tmp_path, acknowledge_gate_not_passed=True, acknowledge_short_paper_run=True)
    s.ctx.env = {"TFM_LIVE": "YES_TRADE_REAL_MONEY"}
    checks = {c.name: c for c in engine.live_clearance(s.ctx)}
    assert checks["gate"].status == "warn" and "ACKNOWLEDGED" in checks["gate"].detail
    assert checks["paper_run"].status == "warn" and checks["confirm_env"].status == "pass"
    s.ctx.env = {}                                                       # an override never covers the env var
    assert {c.name: c for c in engine.live_clearance(s.ctx)}["confirm_env"].status == "fail"


def test_a_real_paper_history_satisfies_the_paper_run_check(tmp_path):
    s = _live_sim(tmp_path, acknowledge_gate_not_passed=True)
    s.ctx.env = {"TFM_LIVE": "YES_TRADE_REAL_MONEY"}
    pdb = Path(s.cfg.db_path_for("paper")); pdb.parent.mkdir(parents=True, exist_ok=True)
    st = Store(str(pdb))
    for i in range(6):
        st.add_equity(f"2026-03-0{i + 1}", 100_000.0, 100_000.0, 0.0, 0.0, "paper")
    c = {c.name: c for c in engine.live_clearance(s.ctx)}["paper_run"]
    assert c.status == "pass" and "6 paper sessions" in c.detail


def test_a_synthetic_gate_report_does_not_count(tmp_path):
    s = _live_sim(tmp_path)
    rd = Path(s.cfg.base_dir, "reports"); rd.mkdir(exist_ok=True)
    (rd / "xs_fake.json").write_text(json.dumps({"name": "fake", "generated_at": "2026-01-01",
        "config": {"data": {"source": "synthetic"}, "forecast": {}}, "gate": {"verdict": "PROCEED"}}))
    assert engine.gate_status(s.cfg, s.ctx.run).status == "fail"


def test_a_real_passing_report_for_the_same_model_passes_the_gate(tmp_path):
    s = _live_sim(tmp_path)
    rd = Path(s.cfg.base_dir, "reports"); rd.mkdir(exist_ok=True)
    fc = s.ctx.run.forecast
    (rd / "xs_real.json").write_text(json.dumps({"name": "real", "generated_at": "2026-02-01",
        "config": {"data": {"source": "equity"}, "forecast": {"forecaster": fc.forecaster, "model_id": fc.model_id}},
        "gate": {"verdict": "PROCEED"}}))
    assert engine.gate_status(s.cfg, s.ctx.run).status == "pass"
    (rd / "xs_real2.json").write_text(json.dumps({"name": "real2", "generated_at": "2026-03-01",
        "config": {"data": {"source": "equity"}, "forecast": {"forecaster": fc.forecaster, "model_id": fc.model_id}},
        "gate": {"verdict": "STOP"}}))
    assert engine.gate_status(s.cfg, s.ctx.run).status == "fail"          # the NEWEST real report decides


def test_small_capital_triggers_a_loud_rounding_warning(tmp_path):
    big = Sim(tmp_path / "big", capital=1_000_000.0)
    small = Sim(tmp_path / "small", capital=4_000.0)
    for s in (big, small):
        s.at(s.evening())
    pb, ps = engine.plan(big.ctx), engine.plan(small.ctx)
    assert pb["payload"]["decision"]["rounding_error"] < 0.05
    assert ps["payload"]["decision"]["rounding_error"] > 0.10
    assert any("whole-share rounding" in n for n in ps["payload"]["decision"]["notes"])
    assert not any("whole-share rounding" in n for n in pb["payload"]["decision"]["notes"])
