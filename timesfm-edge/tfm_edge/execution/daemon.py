"""The scheduler. A loop that wakes every half minute and does whatever is due.

It holds no schedule state of its own: every decision is made from the clock and the ledger, so
a restart in the middle of the evening picks up exactly where the last run stopped, and running
two ticks in a row does nothing the second time.

One failure never stops the loop. An exception in one task is logged to the ledger and the loop
carries on, because a bot that dies silently at 16:20 is worse than one that logs an error and
tries again at 16:50. The exception to that is the live-clearance refusal, which is logged at
critical level so it is impossible to miss.
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta, timezone

from . import engine
from .broker import LiveNotCleared
from .engine import Context
from .sessions import ET, parse_hhmm, to_et

RETRY_BLOCKED_MINUTES = 30


def _safe(ctx: Context, label: str, fn, acts: list[str]):
    try:
        r = fn()
        acts.append(f"{label}: {r.get('status', 'ok') if isinstance(r, dict) else 'ok'}")
        return r
    except LiveNotCleared as e:
        ctx.store.event("critical", "live_refused", f"{label}: {e}")
        acts.append(f"{label}: REFUSED")
    except Exception as e:
        ctx.store.event("error", "daemon_error", f"{label}: {type(e).__name__}: {e}")
        acts.append(f"{label}: ERROR {type(e).__name__}")
    return None


def tick(ctx: Context) -> list[str]:
    cfg, st, cal = ctx.cfg, ctx.store, ctx.calendar
    now = ctx.now()
    et = to_et(now)
    today = et.date()
    sch = cfg.schedule
    acts: list[str] = []

    # 1. reconcile at the configured times, once each
    for hhmm in sch.reconcile_at_et:
        t = parse_hhmm(hhmm)
        key = f"daemon.reconcile.{today}.{hhmm}"
        due = datetime.combine(today, t, tzinfo=ET)
        if cal.is_session(today) and due <= et < due + timedelta(hours=3) and not st.get(key):
            st.set(key, True)
            _safe(ctx, f"reconcile@{hhmm}", lambda: engine.reconcile(ctx), acts)

    # 2. execute an approved plan inside the pre-open window, once
    lo = datetime.combine(today, parse_hhmm(sch.execute_at_et), tzinfo=ET)
    hi = datetime.combine(today, parse_hhmm(sch.execute_cutoff_et), tzinfo=ET)
    if cal.is_session(today) and lo <= et <= hi:
        p = st.latest_plan(("approved",))
        if p and p["for_date"] == today.isoformat():
            _safe(ctx, "execute", lambda: engine.execute(ctx), acts)

    # 3. plan once a session has completed and the data vendor has had time to publish
    expected = cal.last_completed_session(now)
    for_date = cal.next_session(expected)
    cutoff = datetime.combine(for_date, parse_hhmm(sch.execute_cutoff_et), tzinfo=ET)
    after_plan_time = (expected != today) or et.time() >= parse_hhmm(sch.plan_after_et)
    if after_plan_time and et < cutoff:
        latest = st.latest_plan()
        stale = latest is None or latest["asof"] != expected.isoformat()
        retry = False
        if latest and latest["asof"] == expected.isoformat() and latest["status"] == "blocked":
            made = datetime.fromisoformat(latest["created_ts"])
            retry = now - made >= timedelta(minutes=RETRY_BLOCKED_MINUTES)
        if stale or retry:
            _safe(ctx, "plan", lambda: engine.plan(ctx), acts)
    return acts


def run_forever(ctx: Context, poll_s: float = 30.0, log=print) -> None:
    ctx.store.event("info", "daemon_start", f"scheduler started ({ctx.cfg.broker.kind})")
    log(f"scheduler running in {ctx.cfg.broker.kind} mode. Ctrl-C to stop; `touch {ctx.cfg.kill_file}` to halt trading.")
    while True:
        for a in tick(ctx):
            log(f"{datetime.now(timezone.utc):%H:%M:%S}  {a}")
        _time.sleep(poll_s)
