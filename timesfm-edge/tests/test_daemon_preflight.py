from datetime import datetime, time, timedelta
from pathlib import Path

import pytest

from tfm_edge.execution import daemon, engine
from tfm_edge.execution.preflight import run_preflight, verdict
from tfm_edge.execution.sessions import ET, WeekdayCalendar

from .bot_harness import Sim


def plans(acts):
    """Just the plan actions: a running daemon also does any reconcile that has come due."""
    return [a for a in acts if a.startswith("plan")]


def at(sim, d, hh, mm=0):
    sim.t = datetime.combine(d, time(hh, mm), tzinfo=ET)
    return sim.t


# ---- the scheduler ---------------------------------------------------------------------------
def test_tick_plans_after_the_plan_time_and_not_before(tmp_path):
    s = Sim(tmp_path)
    d = s.day(s.k)
    at(s, d, 16, 5)
    assert daemon.tick(s.ctx) == []                                    # market just closed, vendor not ready: wait
    at(s, d, 16, 25)
    first = daemon.tick(s.ctx)
    assert plans(first) == ["plan: approved"] and "reconcile@16:15: ok" in first
    assert daemon.tick(s.ctx) == []                                    # a second tick does nothing at all


def test_tick_executes_inside_the_window_once(tmp_path):
    s = Sim(tmp_path)
    d = s.day(s.k)
    at(s, d, 16, 30); daemon.tick(s.ctx)
    nxt = d + timedelta(days=1)
    at(s, nxt, 8, 0); assert "execute: executed" not in daemon.tick(s.ctx)       # too early
    at(s, nxt, 9, 2)
    assert "execute: executed" in daemon.tick(s.ctx)
    assert all("execute" not in a for a in daemon.tick(s.ctx))                      # already done


def test_tick_never_executes_after_the_cutoff(tmp_path):
    s = Sim(tmp_path)
    d = s.day(s.k)
    at(s, d, 16, 30); daemon.tick(s.ctx)
    at(s, d + timedelta(days=1), 9, 40)
    assert all("execute" not in a for a in daemon.tick(s.ctx))
    assert s.ctx.store.q("SELECT * FROM orders") == []


def test_tick_reconciles_at_each_configured_time_once(tmp_path):
    s = Sim(tmp_path)
    d = s.day(s.k)
    at(s, d, 9, 45)
    assert daemon.tick(s.ctx) == ["reconcile@09:40: ok"] and daemon.tick(s.ctx) == []
    at(s, d, 16, 20)
    assert "reconcile@16:15: ok" in daemon.tick(s.ctx)


def test_a_blocked_plan_is_retried_after_half_an_hour(tmp_path):
    s = Sim(tmp_path)
    d = s.day(s.k)
    boom = {"on": True}
    real = s.ctx.load_panel

    def flaky():
        if boom["on"]:
            raise ConnectionError("vendor down")
        return real()
    s.ctx.load_panel = flaky
    t0 = at(s, d, 16, 30)
    assert plans(daemon.tick(s.ctx)) == ["plan: blocked"]
    s.ctx.store.x("UPDATE plans SET created_ts=?", (t0.isoformat(),))
    at(s, d, 16, 45); assert plans(daemon.tick(s.ctx)) == []           # too soon to retry
    boom["on"] = False
    at(s, d, 17, 5)
    assert plans(daemon.tick(s.ctx)) == ["plan: approved"]             # the vendor came back


def test_one_failing_task_does_not_kill_the_loop(tmp_path):
    s = Sim(tmp_path)
    s.ctx.load_panel = lambda: 1 / 0
    at(s, s.day(s.k), 16, 30)
    acts = daemon.tick(s.ctx)
    # the reconcile task blew up, and the loop still went on to plan (which reported it as blocked)
    assert "reconcile@16:15: ERROR ZeroDivisionError" in acts and plans(acts) == ["plan: blocked"]
    s.ctx.store.x("UPDATE plans SET created_ts=?", ((s.t - timedelta(hours=1)).isoformat(),))
    import tfm_edge.execution.engine as eng
    orig = eng.plan
    eng.plan = lambda ctx, force=False: (_ for _ in ()).throw(RuntimeError("unexpected"))
    try:
        assert plans(daemon.tick(s.ctx)) == ["plan: ERROR RuntimeError"]
    finally:
        eng.plan = orig
    assert any(e["kind"] == "daemon_error" for e in s.ctx.store.events(20))


def test_weekends_are_skipped_by_the_default_calendar():
    cal = WeekdayCalendar()
    from datetime import date
    fri = datetime.combine(date(2026, 3, 6), time(17, 0), tzinfo=ET)
    sat = datetime.combine(date(2026, 3, 7), time(12, 0), tzinfo=ET)
    assert cal.last_completed_session(fri) == date(2026, 3, 6)
    assert cal.last_completed_session(sat) == date(2026, 3, 6)
    assert cal.next_session(date(2026, 3, 6)) == date(2026, 3, 9)
    assert cal.session_label(datetime.combine(date(2026, 3, 9), time(8, 0), tzinfo=ET)) == date(2026, 3, 6)
    assert cal.session_label(datetime.combine(date(2026, 3, 9), time(9, 40), tzinfo=ET)) == date(2026, 3, 9)


# ---- preflight ---------------------------------------------------------------------------------
def probe_ok(url):
    return 200


def test_preflight_passes_on_a_healthy_paper_setup(tmp_path):
    s = Sim(tmp_path); at(s, s.day(s.k), 17, 0)
    checks = run_preflight(s.ctx, probe=probe_ok)
    assert verdict(checks) == "GO", [str(c) for c in checks if c.status == "fail"]
    names = {c.name for c in checks}
    assert {"config", "kill_switch", "data_coverage", "model", "account"} <= names


def test_preflight_fails_when_a_host_is_unreachable(tmp_path):
    s = Sim(tmp_path); at(s, s.day(s.k), 17, 0)
    def probe(url):
        raise ConnectionError("blocked by egress policy")
    checks = run_preflight(s.ctx, probe=probe)
    assert verdict(checks) == "NO-GO" and any(c.name.startswith("net:stooq.com") and c.status == "fail" for c in checks)


def test_preflight_fails_when_the_kill_switch_is_on(tmp_path):
    s = Sim(tmp_path); at(s, s.day(s.k), 17, 0)
    engine.kill(s.ctx, "test")
    assert verdict(run_preflight(s.ctx, probe=probe_ok)) == "NO-GO"


def test_preflight_fails_when_data_is_unavailable(tmp_path):
    s = Sim(tmp_path); at(s, s.day(s.k), 17, 0)
    s.ctx.load_panel = lambda: (_ for _ in ()).throw(ConnectionError("vendor down"))
    checks = run_preflight(s.ctx, probe=probe_ok)
    assert verdict(checks) == "NO-GO" and any(c.name == "data" and c.status == "fail" for c in checks)


def test_preflight_fails_when_the_model_cannot_load(tmp_path):
    s = Sim(tmp_path); at(s, s.day(s.k), 17, 0)
    s.ctx.make_forecaster = lambda: (_ for _ in ()).throw(OSError("weights not found"))
    checks = run_preflight(s.ctx, probe=probe_ok)
    assert any(c.name == "model" and c.status == "fail" and "weights not found" in c.detail for c in checks)


def test_live_preflight_is_no_go_without_the_clearance_items(tmp_path):
    s = Sim(tmp_path, kind="alpaca_live", require_approval=True); at(s, s.day(s.k), 17, 0)
    checks = run_preflight(s.ctx, probe=probe_ok)
    failed = {c.name for c in checks if c.status == "fail"}
    assert verdict(checks) == "NO-GO" and {"confirm_env", "gate", "paper_run"} <= failed
