"""The bot's daily cycle.

    evening   plan()       forecast, decide, size, risk-check; write a PLAN, place no orders
    (you)     approve()    a human reads the plan and approves it (required by default for live)
    pre-open  execute()    re-check everything against fresh account state, then submit orders
    open+     reconcile()  record fills, snapshot equity, place protective brackets, check limits

The split between plan and execute is the point. A decision made at the close is acted on at
the next open (hard constraint 2), and between the two there is a window in which a person, the
kill switch, or the risk checks can stop it.

EVERYTHING THAT CAN ADD RISK PASSES THROUGH execute() AND reconcile()'s bracket placement, and
both are gated by the kill switch and, in live mode, by live_clearance().
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from ..config import RunConfig
from ..data.panel import Panel
from ..decision.book import Decision, decide
from ..risk.brackets import make_bracket
from ..risk.limits import BLOCK, HALT, Violation, check_account, check_plan, has_halt
from .broker import (ENTRY_PREFIX, EXIT_PREFIX, Broker, BrokerError, LiveNotCleared, PaperBroker)
from .config import BotConfig
from .sessions import WeekdayCalendar, parse_hhmm, to_et, ET
from .signals import Signals, asof_date, compute_signals
from .store import Store

LIVE_CONFIRM_ENV, LIVE_CONFIRM_VALUE = "TFM_LIVE", "YES_TRADE_REAL_MONEY"
DEFAULT_SIGMA = 0.02          # used for a bracket when a name has no volatility estimate


@dataclass
class Check:
    name: str
    status: str               # pass | warn | fail
    detail: str

    def __str__(self):
        return f"[{self.status.upper():4}] {self.name}: {self.detail}"


@dataclass
class Context:
    cfg: BotConfig
    run: RunConfig
    store: Store
    broker: Broker
    calendar: WeekdayCalendar
    load_panel: Callable[[], Panel]
    make_forecaster: Callable[[], Any]
    now: Callable[[], datetime]
    env: Mapping[str, str]


# ====================================================================================
# kill switch
# ====================================================================================
def kill_state(ctx: Context) -> dict | None:
    """Active if the KILL file exists OR the ledger says halted. Either is enough."""
    if Path(ctx.cfg.kill_file).exists():
        try:
            reason = Path(ctx.cfg.kill_file).read_text().strip() or "KILL file present"
        except OSError:
            reason = "KILL file present"
        return {"active": True, "source": "file", "reason": reason}
    k = ctx.store.get("kill")
    return k if k and k.get("active") else None


def kill(ctx: Context, reason: str, *, flatten: bool = False, by: str = "system") -> dict:
    """Halt trading. Cancels working ENTRY orders; leaves protective exits in place unless
    flatten=True, which closes every position at market. Reducing risk never needs clearance."""
    st = ctx.store
    st.set("kill", {"active": True, "reason": reason, "by": by, "ts": st.now(), "flatten": flatten})
    cancelled = closed = 0
    try:
        cancelled = ctx.broker.cancel_entry_orders()
        if flatten:
            closed = ctx.broker.close_all_positions()
    except Exception as e:                                          # the halt flag is already set
        st.event("critical", "kill_error", f"halt flag set but broker call failed: {e}")
    st.event("critical", "kill", f"HALT by {by}: {reason}", {"flatten": flatten, "cancelled": cancelled, "closed": closed})
    return {"active": True, "cancelled": cancelled, "closed": closed}


def resume(ctx: Context, confirm: str, by: str = "human") -> dict:
    if confirm != "RESUME":
        raise ValueError("type RESUME to confirm")
    if Path(ctx.cfg.kill_file).exists():
        raise RuntimeError(f"{ctx.cfg.kill_file} exists. Remove it yourself first: that file is the one "
                           f"switch this program will never clear for you.")
    ctx.store.set("kill", {"active": False, "by": by, "ts": ctx.store.now()})
    ctx.store.event("warn", "resume", f"trading resumed by {by}")
    return {"active": False}


# ====================================================================================
# live clearance: what stands between this code and real money
# ====================================================================================
def paper_sessions(cfg: BotConfig) -> int:
    """Most distinct sessions of equity history across the paper ledgers."""
    best = 0
    for kind in ("paper", "alpaca_paper"):
        p = cfg.db_path_for(kind)
        if not Path(p).exists():
            continue
        try:
            db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            n = db.execute("SELECT COUNT(DISTINCT session) FROM equity").fetchone()[0]
            db.close()
            best = max(best, int(n or 0))
        except sqlite3.Error:
            continue
    return best


def gate_status(cfg: BotConfig, run: RunConfig) -> Check:
    """Is there a passing Phase 1 report, on REAL data, for this configuration?"""
    reports = sorted(Path(cfg.base_dir, "reports").glob("xs_*.json"))
    best: dict | None = None
    for p in reports:
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if d.get("config", {}).get("data", {}).get("source") in ("synthetic", None):
            continue                                                 # a synthetic pass proves nothing here
        if best is None or d.get("generated_at", "") > best.get("generated_at", ""):
            best = d
    if best is None:
        return Check("gate", "fail", "no Phase 1 report on real data exists. The edge has not been measured.")
    verdict = best.get("gate", {}).get("verdict", "?")
    fc = best.get("config", {}).get("forecast", {})
    if fc.get("forecaster") != run.forecast.forecaster or fc.get("model_id") != run.forecast.model_id:
        return Check("gate", "fail", f"latest real-data report ({best.get('name')}: {verdict}) is for a "
                                     f"different model than this bot uses")
    if verdict.startswith("PROCEED"):
        return Check("gate", "pass", f"{best.get('name')}: {verdict}")
    return Check("gate", "fail", f"{best.get('name')}: verdict {verdict}. The measured result says no edge, or "
                                 f"too little data to tell.")


def live_clearance(ctx: Context) -> list[Check]:
    """The checks that must pass before any risk-adding live order. Cheap enough to run on every
    execute. Preflight runs these plus deeper ones. Each failed check names its own override."""
    cfg, out = ctx.cfg, []
    if not cfg.is_live:
        return [Check("mode", "pass", f"{cfg.broker.kind}: no real money")]
    out.append(Check("confirm_env", "pass" if ctx.env.get(LIVE_CONFIRM_ENV) == LIVE_CONFIRM_VALUE else "fail",
                     f"set {LIVE_CONFIRM_ENV}={LIVE_CONFIRM_VALUE} in the environment of the process that trades"
                     if ctx.env.get(LIVE_CONFIRM_ENV) != LIVE_CONFIRM_VALUE else "set"))
    k = kill_state(ctx)
    out.append(Check("kill_switch", "fail" if k else "pass", f"ACTIVE: {k['reason']}" if k else "off"))

    g = gate_status(cfg, ctx.run)
    if g.status == "fail" and cfg.live.acknowledge_gate_not_passed:
        g = Check("gate", "warn", f"ACKNOWLEDGED OVERRIDE (live.acknowledge_gate_not_passed): {g.detail}")
    out.append(g)

    days = paper_sessions(cfg)
    if days >= cfg.live.min_paper_days:
        out.append(Check("paper_run", "pass", f"{days} paper sessions >= {cfg.live.min_paper_days}"))
    elif cfg.live.acknowledge_short_paper_run:
        out.append(Check("paper_run", "warn", f"ACKNOWLEDGED OVERRIDE (live.acknowledge_short_paper_run): "
                                              f"only {days} paper sessions, wanted {cfg.live.min_paper_days}"))
    else:
        out.append(Check("paper_run", "fail", f"only {days} paper sessions, need {cfg.live.min_paper_days}. "
                                              f"Run the bot in paper or alpaca_paper mode first."))
    if not cfg.live.require_approval:
        out.append(Check("approval", "warn", "require_approval is OFF: plans execute without a human reading them"))
    return out


def _ensure_cleared(ctx: Context) -> None:
    checks = live_clearance(ctx)
    bad = [c for c in checks if c.status == "fail"]
    if bad:
        ctx.store.event("critical", "live_refused", "live trading refused", [str(c) for c in bad])
        raise LiveNotCleared("live trading refused:\n  " + "\n  ".join(str(c) for c in bad))
    for c in checks:
        if c.status == "warn":
            ctx.store.event("warn", "live_override", str(c))
    if hasattr(ctx.broker, "live_cleared"):
        ctx.broker.live_cleared = True


# ====================================================================================
# helpers
# ====================================================================================
def _managed(ctx: Context) -> set[str]:
    return {s.upper() for s in (ctx.run.cross_section.symbols or [])}


def _positions(ctx: Context) -> dict:
    """Only positions in the bot's own universe. Anything else in the account is not ours to
    trade, and treating it as 'no longer scorable' would make the bot liquidate it."""
    managed = _managed(ctx)
    return {s: p for s, p in ctx.broker.get_positions().items() if s in managed}


def _capital(ctx: Context, equity: float) -> float:
    return float(min(ctx.cfg.capital, equity, ctx.cfg.risk.max_capital))


def _order_ref(plan_id: int, symbol: str) -> str:
    return f"{ENTRY_PREFIX}{plan_id}-{symbol}"


def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def _block(ctx: Context, asof: str, for_date: str, reasons: list[str], extra: dict | None = None) -> dict:
    payload = {"reasons": reasons, "mode": ctx.cfg.broker.kind, **(extra or {})}
    pid = ctx.store.add_plan(asof, for_date, "blocked", ctx.cfg.broker.kind, payload, note="; ".join(reasons))
    ctx.store.event("warn", "plan_blocked", "; ".join(reasons), {"plan_id": pid})
    return ctx.store.plan(pid)


# ====================================================================================
# reconcile
# ====================================================================================
def reconcile(ctx: Context, panel: Panel | None = None) -> dict:
    cfg, st, br = ctx.cfg, ctx.store, ctx.broker
    now = ctx.now()
    out: dict = {"fills": []}

    if isinstance(br, PaperBroker):
        panel = panel if panel is not None else ctx.load_panel()
        out["fills"] = _settle_paper(ctx, panel)
    else:
        out["synced"] = _sync_orders(ctx)

    acct = br.get_account()
    pos = _positions(ctx)
    gross = sum(abs(p.market_value) for p in pos.values())
    net = sum(p.market_value for p in pos.values())
    session = ctx.calendar.session_label(now).isoformat()
    st.add_equity(session, acct.equity, acct.cash, gross, net, cfg.broker.kind)

    prior = [e for e in st.equity_by_session() if e["session"] < session]
    day_start = prior[-1]["equity"] if prior else None
    peak = max([e["equity"] for e in st.equity_by_session()] + [acct.equity, cfg.capital])
    viol = check_account(acct.equity, day_start, peak, cfg.risk)
    out["violations"] = [str(v) for v in viol]
    if has_halt(viol) and not kill_state(ctx):
        kill(ctx, "; ".join(v.detail for v in viol), flatten=cfg.risk.flatten_on_halt, by="risk")

    out["brackets"] = _maintain_brackets(ctx, pos)        # reduces risk, so it runs even when halted
    out.update(equity=acct.equity, session=session, positions=len(pos))
    st.event("info", "reconcile", f"equity {acct.equity:,.2f}, {len(pos)} positions, session {session}")
    return out


def _settle_paper(ctx: Context, panel: Panel) -> list[str]:
    br: PaperBroker = ctx.broker                                       # type: ignore[assignment]
    st = ctx.store
    last = st.get("paper.last_session")
    dates = [str(np.datetime_as_string(t, unit="D")) for t in panel.open_time]
    todo = [i for i, d in enumerate(dates) if (last is None and i == len(dates) - 1) or (last is not None and d > last)]
    log: list[str] = []
    for i in todo:
        d = date.fromisoformat(dates[i])
        bars = {}
        for a, s in enumerate(panel.symbols):
            if not np.isfinite(panel.log_close[i, a]):
                continue
            o, c = float(np.exp(panel.log_open[i, a])), float(np.exp(panel.log_close[i, a]))
            h = float(np.exp(panel.log_high[i, a])) if panel.log_high is not None and np.isfinite(panel.log_high[i, a]) else max(o, c)
            l = float(np.exp(panel.log_low[i, a])) if panel.log_low is not None and np.isfinite(panel.log_low[i, a]) else min(o, c)
            bars[s] = {"open": o, "high": h, "low": l, "close": c}
        log += br.settle_session(dates[i], ctx.calendar.open_utc(d), bars)
    for line in log:
        st.event("info", "paper_fill", line)
    return log


def _sync_orders(ctx: Context) -> int:
    """Pull our orders from the broker and record their state and fills."""
    st, br = ctx.store, ctx.broker
    since = st.get("sync.since") or (ctx.now().astimezone(timezone.utc) - timedelta(days=3)).isoformat()
    n = 0
    for o in br.get_orders_since(since):
        if not o.client_id.startswith((ENTRY_PREFIX, EXIT_PREFIX)):
            continue
        if not st.order_exists(o.client_id):
            st.add_order(plan_id=None, client_id=o.client_id, broker_id=o.id, symbol=o.symbol, side=o.side,
                         qty=o.qty, kind=o.kind, tif=o.tif, status=o.status, raw=o.raw)
        st.update_order(o.client_id, broker_id=o.id, status=o.status, filled_qty=o.filled_qty,
                        filled_avg=o.filled_avg_price)
        if o.filled_qty > 0 and o.filled_avg_price:
            st.add_fill(o.client_id, o.symbol, o.side, o.filled_qty, o.filled_avg_price,
                        o.raw.get("filled_at") or st.now())
        n += 1
    st.set("sync.since", (ctx.now().astimezone(timezone.utc) - timedelta(days=1)).isoformat())
    return n


def _maintain_brackets(ctx: Context, pos: dict) -> dict:
    """Every position gets a stop and a target set at entry time; closed positions lose theirs."""
    st, br, cfg = ctx.store, ctx.broker, ctx.cfg
    have = st.brackets()
    sigma = st.get("last_sigma", {})
    placed = dropped = failed = 0
    for sym in sorted(set(have) - set(pos)):
        try:
            br.cancel_exit_for(sym)
        except BrokerError:
            pass
        st.drop_bracket(sym)
        dropped += 1
    for sym, p in sorted(pos.items()):
        if not p.qty:
            continue
        side = "long" if p.qty > 0 else "short"
        b = have.get(sym)
        if b and b["side"] == side and abs(b["qty"] - abs(p.qty)) < 1e-9:
            continue
        sg = sigma.get(sym, DEFAULT_SIGMA)
        try:
            br.cancel_exit_for(sym)
            bk = make_bracket(p.avg_price, side, sg, cfg.risk)
            stop, target = round(bk.stop, 2), round(bk.target, 2)
            cid = f"{EXIT_PREFIX}{ctx.now().strftime('%Y%m%d%H%M%S')}-{sym}"
            o = br.submit_exit_bracket(sym, int(abs(p.qty)), "sell" if p.qty > 0 else "buy", stop, target, cid)
            st.add_order(plan_id=None, client_id=cid, broker_id=o.id, symbol=sym, side=o.side, qty=abs(p.qty),
                         kind="oco", tif="gtc", status=o.status, raw={"stop": stop, "target": target})
            st.set_bracket(sym, side, abs(p.qty), p.avg_price, stop, target, o.id)
            placed += 1
        except (BrokerError, ValueError) as e:
            failed += 1
            st.event("error", "bracket_failed", f"{sym}: {e}")
    if failed:
        st.event("error", "unprotected", f"{failed} position(s) have no protective bracket")
    return {"placed": placed, "dropped": dropped, "failed": failed}


# ====================================================================================
# plan
# ====================================================================================
def plan(ctx: Context, force: bool = False) -> dict:
    cfg, st, run = ctx.cfg, ctx.store, ctx.run
    now = ctx.now()
    expected = ctx.calendar.last_completed_session(now)
    for_date = ctx.calendar.next_session(expected)

    existing = st.latest_plan(("pending", "approved", "executed", "noop"))
    if existing and existing["asof"] == expected.isoformat() and not force:
        return existing

    k = kill_state(ctx)
    if k:
        return _block(ctx, expected.isoformat(), for_date.isoformat(), [f"kill switch active: {k['reason']}"])

    try:
        panel = ctx.load_panel()
    except Exception as e:
        return _block(ctx, expected.isoformat(), for_date.isoformat(), [f"could not load bars: {type(e).__name__}: {e}"])

    rec = reconcile(ctx, panel)
    refresh_divergence(ctx, panel)
    if kill_state(ctx):
        return _block(ctx, expected.isoformat(), for_date.isoformat(),
                      ["halted during reconcile: " + "; ".join(rec.get("violations", []))])

    reasons: list[str] = []
    asof = asof_date(panel)
    if asof != expected.isoformat() and not force:
        reasons.append(f"stale data: last bar is {asof} but the last completed session is {expected}")
    n_conf = len(_managed(ctx))
    sig = compute_signals(panel, forecaster=ctx.make_forecaster(), context_len=run.forecast.context_len,
                          horizon=run.forecast.horizon, residualise=run.cross_section.residualise,
                          smoothing_halflife=cfg.smoothing_halflife, warmup_days=cfg.score_warmup_days,
                          beta_window=cfg.beta_window, vol_window=cfg.vol_window, n_configured=n_conf)
    if sig.coverage < cfg.min_coverage:
        reasons.append(f"coverage {sig.coverage:.0%} < {cfg.min_coverage:.0%}: {int(sig.coverage * n_conf)} of "
                       f"{n_conf} symbols have a bar for {sig.asof}")
    if not sig.scores:
        reasons.append("no scores could be computed")
    if reasons:
        return _block(ctx, sig.asof, for_date.isoformat(), reasons, {"coverage": sig.coverage})

    acct = ctx.broker.get_account()
    if acct.trading_blocked:
        return _block(ctx, sig.asof, for_date.isoformat(), [f"broker account is blocked (status {acct.status})"])
    capital = _capital(ctx, acct.equity)
    pos = _positions(ctx)
    prices = dict(sig.prices)
    for s, p in pos.items():
        prices.setdefault(s, p.current_price or p.avg_price)

    cur_qty = {s: int(p.qty) for s, p in pos.items()}
    cur_w = {s: q * prices.get(s, 0.0) / capital for s, q in cur_qty.items()}

    # what may we open, on which side?
    can_long, can_short, excluded = set(), set(), []
    for s in sorted(sig.scores):
        try:
            info = ctx.broker.asset_info(s)
        except BrokerError:
            info = None
        if info is None or not info.tradable:
            excluded.append(s); continue
        if sig.prices.get(s, 0) < cfg.risk.min_price:
            excluded.append(s); continue
        can_long.add(s)
        if info.shortable and info.easy_to_borrow:
            can_short.add(s)

    last_reb = st.last_rebalance()
    since = (ctx.calendar.sessions_between(date.fromisoformat(last_reb), date.fromisoformat(sig.asof))
             if last_reb else 10 ** 9)
    dec = decide(sig.scores, cur_w, cfg.book, run.costs, can_long=can_long, can_short=can_short,
                 forecast_bps=sig.forecast_bps, sessions_since_rebalance=since)

    # weights -> whole shares
    tgt_qty: dict[str, int] = {}
    notes = list(dec.notes)
    for s in sorted(set(dec.target) | set(cur_qty)):
        px = prices.get(s)
        want = int(round(dec.target.get(s, 0.0) * capital / px)) if px else 0
        have = cur_qty.get(s, 0)
        if want and have and (want > 0) != (have > 0):
            notes.append(f"{s}: reversal deferred (close now, reopen on the next plan)")
            want = 0
        tgt_qty[s] = want

    # How far does whole-share rounding pull the book from its intended weights? At small capital
    # a 28-name book has ~$500 slots, and a $300 stock rounds to 1 share or 2: a large error.
    intended = sum(abs(w) * capital for w in dec.target.values())
    drift = sum(abs(dec.target.get(s, 0.0) * capital - tgt_qty.get(s, 0) * prices.get(s, 0.0))
                for s in set(dec.target) | set(tgt_qty) if s in prices)
    rounding = drift / intended if intended > 0 else 0.0
    if rounding > 0.10:
        notes.append(f"whole-share rounding moves {rounding:.0%} of intended exposure away from target weights; "
                     f"this capital is small for {len(dec.target)} names, so expect tracking error against the backtest")

    orders = []
    for s in sorted(tgt_qty):
        delta = tgt_qty[s] - cur_qty.get(s, 0)
        if delta:
            orders.append({"symbol": s, "side": "buy" if delta > 0 else "sell", "qty": abs(delta),
                           "ref_price": prices.get(s), "notional": abs(delta) * prices.get(s, 0.0),
                           "from": cur_qty.get(s, 0), "to": tgt_qty[s]})

    viol = check_plan({s: q for s, q in tgt_qty.items() if q}, cur_qty, prices, capital, cfg.risk)
    ranked = sorted(sig.scores, key=lambda s: (sig.scores[s], s))
    payload = {
        "mode": cfg.broker.kind, "capital": capital, "asof": sig.asof, "for_date": for_date.isoformat(),
        "model": sig.model, "coverage": sig.coverage, "n_scored": len(sig.scores),
        "orders": orders, "target_qty": {s: q for s, q in tgt_qty.items() if q}, "current_qty": cur_qty,
        "prices": {s: prices[s] for s in tgt_qty if s in prices},
        "decision": {"rebalanced": dec.rebalanced, "turnover": dec.turnover, "names_changed": dec.names_changed,
                     "fraction_changed": dec.fraction_changed(len(sig.scores)), "rounding_error": rounding,
                     "n_long": dec.n_long,
                     "n_short": dec.n_short, "gross": dec.gross, "net": dec.net, "notes": notes,
                     "excluded": excluded},
        "top": [(s, sig.scores[s], sig.forecast_bps.get(s)) for s in reversed(ranked[-8:])],
        "bottom": [(s, sig.scores[s], sig.forecast_bps.get(s)) for s in ranked[:8]],
        "violations": [str(v) for v in viol],
        "require_approval": cfg.live.require_approval,
        "fingerprint": hashlib.sha256(json.dumps([sig.asof, sorted(sig.scores.items()), cur_qty, capital],
                                                 sort_keys=True, default=str).encode()).hexdigest()[:16],
    }

    # persist what the bot saw and decided, whatever happens next
    ts = st.now()
    with st.tx() as db:
        for s, v in sig.scores.items():
            db.execute("INSERT OR REPLACE INTO scores(asof,symbol,raw,smoothed,forecast_bps) VALUES(?,?,?,?,?)",
                       (sig.asof, s, sig.raw.get(s), v, sig.forecast_bps.get(s)))
        for s, q in sig.quantiles.items():
            db.execute("INSERT INTO forecasts(ts,asof,symbol,model,point,quantiles) VALUES(?,?,?,?,?,?)",
                       (ts, sig.asof, s, sig.model, sig.forecast_bps.get(s, 0) / 1e4, json.dumps(q)))
    st.set("last_sigma", sig.sigma)

    if viol:
        return _block(ctx, sig.asof, for_date.isoformat(), [str(v) for v in viol], payload)

    st.set_ideal(for_date.isoformat(), sig.asof, dec.target)
    if dec.rebalanced:
        st.mark_rebalance(sig.asof)

    if not orders:
        status = "noop"
    elif cfg.live.require_approval:
        status = "pending"
    else:
        status = "approved"
    pid = st.add_plan(sig.asof, for_date.isoformat(), status, cfg.broker.kind, payload)
    if status == "approved":
        st.set_plan_status(pid, "approved", approved_ts=ts, approved_by="auto")
    st.event("info", "plan", f"plan {pid} for {for_date}: {len(orders)} orders, turnover {dec.turnover:.2f}, "
                             f"{dec.n_long}L/{dec.n_short}S, status {status}", {"plan_id": pid})
    if cfg.is_live and not cfg.live.require_approval:
        st.event("warn", "no_approval", "live plan will execute without human approval")
    return st.plan(pid)


def refresh_divergence(ctx: Context, panel: Panel) -> dict | None:
    """Recompute live-vs-shadow-vs-backtest and cache it for the UI; write the daily report file."""
    from ..analysis import divergence as dv
    try:
        exp = dv.backtest_expectation(ctx.cfg.base_dir, ctx.run.forecast.forecaster, ctx.run.forecast.model_id)
        res = dv.compute(ctx.store, panel, capital=ctx.cfg.capital,
                         round_trip_frac=ctx.run.costs.round_trip_frac(), expectation=exp)
        ctx.store.set("divergence.latest", res)
        dv.write_daily_report(res, Path(ctx.cfg.base_dir) / "reports" / "live" /
                              f"{ctx.cfg.name}-{asof_date(panel)}.md", mode=ctx.cfg.broker.kind, name=ctx.cfg.name)
        return res
    except Exception as e:                                           # a report must never stop trading logic
        ctx.store.event("warn", "divergence_failed", f"{type(e).__name__}: {e}")
        return None


def approve(ctx: Context, plan_id: int, by: str = "human") -> dict:
    p = ctx.store.plan(plan_id)
    if not p:
        raise KeyError(plan_id)
    if p["status"] != "pending":
        raise ValueError(f"plan {plan_id} is {p['status']}, only a pending plan can be approved")
    ctx.store.set_plan_status(plan_id, "approved", approved_ts=ctx.store.now(), approved_by=by)
    ctx.store.event("info", "approve", f"plan {plan_id} approved by {by}")
    return ctx.store.plan(plan_id)


def reject(ctx: Context, plan_id: int, by: str = "human") -> dict:
    p = ctx.store.plan(plan_id)
    if not p or p["status"] not in ("pending", "approved"):
        raise ValueError("only a pending or approved plan can be rejected")
    ctx.store.set_plan_status(plan_id, "rejected", note=f"rejected by {by}")
    ctx.store.event("info", "reject", f"plan {plan_id} rejected by {by}")
    return ctx.store.plan(plan_id)


# ====================================================================================
# execute
# ====================================================================================
def execute(ctx: Context) -> dict:
    cfg, st, br = ctx.cfg, ctx.store, ctx.broker
    now = ctx.now()
    p = st.latest_plan(("approved",))
    if not p:
        return {"status": "no_approved_plan"}
    pid, pl = p["id"], p["payload"]

    cutoff = datetime.combine(date.fromisoformat(p["for_date"]), parse_hhmm(cfg.schedule.execute_cutoff_et), tzinfo=ET)
    if now > cutoff:
        st.set_plan_status(pid, "expired", note=f"not executed before {cutoff.isoformat()}")
        st.event("warn", "plan_expired", f"plan {pid} expired unexecuted: a decision is never run late")
        return {"status": "expired", "plan_id": pid}

    def refuse(reason: str, status: str = "blocked") -> dict:
        st.set_plan_status(pid, status, note=reason)
        st.event("warn", "execute_refused", f"plan {pid}: {reason}")
        return {"status": status, "plan_id": pid, "reason": reason}

    k = kill_state(ctx)
    if k:
        return refuse(f"kill switch active: {k['reason']}")
    if cfg.is_live:
        _ensure_cleared(ctx)

    acct = br.get_account()
    if acct.trading_blocked:
        return refuse(f"account blocked ({acct.status})")
    eq = st.equity_by_session()
    peak = max([e["equity"] for e in eq] + [acct.equity, cfg.capital])
    prior = [e for e in eq if e["session"] < ctx.calendar.session_label(now).isoformat()]
    viol = check_account(acct.equity, prior[-1]["equity"] if prior else None, peak, cfg.risk)
    if has_halt(viol):
        kill(ctx, "; ".join(v.detail for v in viol), flatten=cfg.risk.flatten_on_halt, by="risk")
        return refuse("; ".join(str(v) for v in viol))

    cur_now = {s: int(q.qty) for s, q in _positions(ctx).items()}
    if {s: q for s, q in cur_now.items() if q} != {s: q for s, q in pl["current_qty"].items() if q}:
        return refuse("positions changed since this plan was made; plan again")

    capital = _capital(ctx, acct.equity)
    prices = pl["prices"]
    viol = check_plan(pl["target_qty"], cur_now, prices, capital, cfg.risk)
    if viol:
        return refuse("; ".join(str(v) for v in viol))

    results, errors = [], []
    for o in pl["orders"]:
        cid = _order_ref(pid, o["symbol"])
        if st.order_exists(cid):
            results.append((o["symbol"], "already_submitted"))
            continue
        try:
            if o["symbol"] in st.brackets():
                br.cancel_exit_for(o["symbol"])
                st.drop_bracket(o["symbol"])
            bo = br.submit_order(o["symbol"], o["side"], int(o["qty"]), tif=cfg.broker.order_tif, client_id=cid)
            st.add_order(plan_id=pid, client_id=cid, broker_id=bo.id, symbol=o["symbol"], side=o["side"],
                         qty=o["qty"], kind="market", tif=cfg.broker.order_tif, status=bo.status, raw=bo.raw)
            results.append((o["symbol"], bo.status))
        except LiveNotCleared:
            raise
        except BrokerError as e:
            errors.append(f"{o['symbol']}: {e}")
            st.event("error", "order_failed", f"{o['symbol']}: {e}")
    status = "executed" if not errors else "partial"
    st.set_plan_status(pid, status, executed_ts=st.now(), note="; ".join(errors))
    st.event("info" if not errors else "error", "execute",
             f"plan {pid}: {len(results)} orders submitted, {len(errors)} failed", {"errors": errors})
    return {"status": status, "plan_id": pid, "submitted": len(results), "errors": errors}


# ====================================================================================
# context
# ====================================================================================
def build_context(cfg: BotConfig, *, env: Mapping[str, str] | None = None, now: Callable | None = None,
                  broker: Broker | None = None, load_panel: Callable | None = None,
                  make_forecaster: Callable | None = None, calendar=None, store: Store | None = None,
                  log=print) -> Context:
    from ..data.equity import equity_panel
    from ..model.factory import make_forecaster as _mf
    from .broker import AlpacaBroker

    env = env if env is not None else os.environ
    run = cfg.run()
    now_fn = now or (lambda: datetime.now(timezone.utc))
    store = store or Store(cfg.db_path)

    if broker is None:
        if cfg.broker.kind == "paper":
            broker = PaperBroker(store, cfg.capital, run.costs, now_fn=now_fn)
        else:
            key, secret = env.get(cfg.broker.key_env), env.get(cfg.broker.secret_env)
            if not key or not secret:
                raise BrokerError(f"set {cfg.broker.key_env} and {cfg.broker.secret_env} in the environment")
            broker = AlpacaBroker(cfg.broker.kind, key, secret, base_url=cfg.broker.base_url,
                                  timeout=cfg.broker.request_timeout_s)

    def _panel() -> Panel:
        return equity_panel(sorted(_managed_from(run)), source=run.data.equity_source, years=cfg.data_years,
                            cache_dir=str(Path(cfg.base_dir) / run.data.cache_dir),
                            universe_path=run.cross_section.universe_path,
                            min_names_per_bar=run.cross_section.min_names_per_bar, log=lambda *a: None,
                            max_age_hours=cfg.data_max_age_hours)

    return Context(cfg=cfg, run=run, store=store, broker=broker, calendar=calendar or WeekdayCalendar(),
                   load_panel=load_panel or _panel,
                   make_forecaster=make_forecaster or (lambda: _mf(run.forecast)), now=now_fn, env=env)


def _managed_from(run: RunConfig) -> set[str]:
    return {s.upper() for s in (run.cross_section.symbols or [])}
