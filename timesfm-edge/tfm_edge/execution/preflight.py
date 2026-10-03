"""GO / NO-GO. Run before each stage: paper, alpaca_paper, live.

Every check is something that, if wrong, produces a silent failure rather than an error:
a bot that cannot reach its data plans nothing and you do not notice; a model that fails to
load only fails at the first real plan; an account with shorting disabled rejects half the
book. Better to learn that here, with no orders in flight.
"""
from __future__ import annotations

from typing import Callable

import requests

from ..analysis import divergence as dv
from . import engine
from .broker import AlpacaBroker, BrokerError
from .engine import Check, Context
from .store import Store

STOOQ = "https://stooq.com/q/d/l/?s=aapl.us&i=d"
HF_META = "https://huggingface.co/api/models/google/timesfm-2.5-200m-pytorch"
HF_CDN = "https://cas-bridge.xethub.hf.co/"
ALPACA_PAPER, ALPACA_LIVE = "https://paper-api.alpaca.markets/v2/clock", "https://api.alpaca.markets/v2/clock"


def _reach(url: str, probe: Callable[[str], int]) -> Check:
    host = url.split("/")[2]
    try:
        code = probe(url)
    except Exception as e:
        return Check(f"net:{host}", "fail", f"{type(e).__name__}: {str(e)[:120]}")
    return Check(f"net:{host}", "pass", f"reachable (HTTP {code})")


def _http_status(url: str) -> int:
    return requests.get(url, timeout=15, allow_redirects=True, stream=True).status_code


def run_preflight(ctx: Context, *, probe: Callable[[str], int] = _http_status, deep: bool = True) -> list[Check]:
    cfg, run, st = ctx.cfg, ctx.run, ctx.store
    out: list[Check] = []
    add = out.append

    add(Check("config", "pass", f"{cfg.name}: {cfg.broker.kind}, capital ${cfg.capital:,.0f} "
                                f"(ceiling ${cfg.risk.max_capital:,.0f}), daily loss limit {cfg.risk.daily_loss_limit:.1%}, "
                                f"drawdown halt {cfg.risk.max_drawdown_halt:.0%}"))
    k = engine.kill_state(ctx)
    add(Check("kill_switch", "fail" if k else "pass", f"ACTIVE: {k['reason']}" if k else "off"))

    # --- network ---------------------------------------------------------------------------
    hosts = [STOOQ]
    if run.forecast.forecaster == "timesfm":
        hosts += [HF_META, HF_CDN]
    if cfg.broker.kind != "paper" and not cfg.broker.base_url:
        hosts.append(ALPACA_LIVE if cfg.is_live else ALPACA_PAPER)
    for h in hosts:
        add(_reach(h, probe))

    # --- data --------------------------------------------------------------------------------
    panel = None
    try:
        panel = ctx.load_panel()
        expected = ctx.calendar.last_completed_session(ctx.now()).isoformat()
        sig_asof = engine.asof_date(panel)
        member = panel.membership()
        cov = member[-1].sum() / max(len(engine._managed(ctx)), 1)
        add(Check("data_fresh", "pass" if sig_asof == expected else "warn",
                  f"last bar {sig_asof}, last completed session {expected}"
                  + ("" if sig_asof == expected else " (fine before the data vendor publishes; a plan will wait)")))
        add(Check("data_coverage", "pass" if cov >= cfg.min_coverage else "fail",
                  f"{cov:.0%} of {len(engine._managed(ctx))} symbols have a bar (need {cfg.min_coverage:.0%})"))
    except Exception as e:
        add(Check("data", "fail", f"could not load bars: {type(e).__name__}: {str(e)[:160]}"))

    # --- model ---------------------------------------------------------------------------------
    if deep:
        try:
            import numpy as np
            fc = ctx.make_forecaster()
            fc.fit(np.random.default_rng(0).standard_normal(500) * 0.01)
            w = np.cumsum(np.random.default_rng(1).standard_normal(256) * 0.01)
            d = fc.predict([w], run.forecast.horizon)
            ok = d.quantiles.shape == (1, 9) and bool(np.isfinite(d.point).all())
            add(Check("model", "pass" if ok else "fail",
                      f"{getattr(fc, 'version', fc.name)} produced a forecast" if ok else "forecast malformed"))
        except Exception as e:
            add(Check("model", "fail", f"{type(e).__name__}: {str(e)[:200]}"))

    # --- broker account ------------------------------------------------------------------------
    if cfg.broker.kind != "paper":
        try:
            a = ctx.broker.get_account()
            add(Check("account", "fail" if (a.trading_blocked or a.status != "ACTIVE") else "pass",
                      f"status {a.status}, equity ${a.equity:,.2f}, cash ${a.cash:,.2f}, "
                      f"buying power ${a.buying_power:,.2f}, multiplier {a.multiplier:g}"))
            add(Check("shorting", "pass" if a.shorting_enabled else "fail",
                      "enabled" if a.shorting_enabled else "DISABLED: a long/short book needs a margin account with shorting"))
            add(Check("capital_vs_equity", "pass" if a.equity >= cfg.capital else "warn",
                      f"equity ${a.equity:,.0f} vs configured capital ${cfg.capital:,.0f}"
                      + ("" if a.equity >= cfg.capital else "; the bot will size to the smaller number")))
            if a.pattern_day_trader or a.equity < 25_000:
                add(Check("pdt", "warn", "under $25k equity the pattern-day-trader rule applies: a stop that fires on the "
                                         "day a position was opened counts as a day trade"))
            pos = ctx.broker.get_positions()
            foreign = sorted(set(pos) - engine._managed(ctx))
            if foreign:
                add(Check("foreign_positions", "warn", f"{len(foreign)} position(s) outside the bot's universe "
                                                      f"({', '.join(foreign[:6])}); they will be left alone. Use a dedicated "
                                                      f"account if you can."))
            if engine._positions(ctx):
                add(Check("existing_positions", "warn", f"{len(engine._positions(ctx))} position(s) in the bot's universe "
                                                        f"already; the bot will manage them as its own"))
            sample = sorted(engine._managed(ctx))[:12]
            htb = [s for s in sample if not _safe_shortable(ctx.broker, s)]
            add(Check("borrow", "warn" if htb else "pass",
                      f"{len(htb)} of {len(sample)} sampled names not easy to borrow: {', '.join(htb)}" if htb
                      else f"all {len(sample)} sampled names shortable"))
        except BrokerError as e:
            add(Check("account", "fail", str(e)[:200]))
    else:
        add(Check("account", "pass", "paper simulator (no broker account)"))

    # --- what protects real money --------------------------------------------------------------
    if cfg.is_live or cfg.broker.kind == "alpaca_paper":
        for c in engine.live_clearance(ctx):
            out.append(c)
    if cfg.is_live:
        if panel is not None:
            add(_divergence_check(ctx, panel))
    return out


def _safe_shortable(broker, s: str) -> bool:
    try:
        i = broker.asset_info(s)
        return bool(i.tradable and i.shortable and i.easy_to_borrow)
    except Exception:
        return False


def _divergence_check(ctx: Context, panel) -> Check:
    """Does the best paper run so far track its own ideal book? Live inherits that evidence."""
    cfg = ctx.cfg
    best = None
    for kind in ("paper", "alpaca_paper"):
        import os
        p = cfg.db_path_for(kind)
        if not os.path.exists(p):
            continue
        s = Store(p)
        n = len(s.equity_by_session())
        if best is None or n > best[0]:
            best = (n, s, kind)
    if best is None or best[0] < 3:
        return Check("paper_divergence", "warn", "not enough paper history to measure tracking against the ideal book")
    n, s, kind = best
    res = dv.compute(s, panel, capital=cfg.capital, round_trip_frac=ctx.run.costs.round_trip_frac())
    if not res.get("n"):
        return Check("paper_divergence", "warn", res.get("note", "no overlap"))
    z = res.get("z_gap")
    bad = z is not None and abs(z) > cfg.live.max_divergence_z
    return Check("paper_divergence", "fail" if bad else "pass",
                 f"{kind}: {res['n']} sessions, mean gap {res['mean_gap_bps']:+.2f} bps/day"
                 + (f", z {z:+.2f} (limit {cfg.live.max_divergence_z})" if z is not None else ""))


def verdict(checks: list[Check]) -> str:
    return "NO-GO" if any(c.status == "fail" for c in checks) else "GO"
