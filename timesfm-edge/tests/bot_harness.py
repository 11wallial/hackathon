"""Replay a synthetic market through the real engine, one session at a time.

Time and bars are injected: the engine never knows it is in a simulation. `Sim.k` is the index
of the last bar that has been "published", and the panel handed to the engine ends there, so
the engine can only ever see what a real run on that evening would have seen.
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import yaml

from tfm_edge.data.panel import Panel, generate_panel
from tfm_edge.decision.book import BookConfig
from tfm_edge.execution.config import BotConfig, BrokerConfig, LiveGuard
from tfm_edge.execution.engine import Context, build_context
from tfm_edge.execution.sessions import ET, EveryDayCalendar
from tfm_edge.execution.store import Store
from tfm_edge.risk.limits import RiskConfig

N_ASSETS = 30


def slice_panel(p: Panel, k: int) -> Panel:
    n = k + 1
    f = lambda a: None if a is None else a[:n]
    return dataclasses.replace(p, open_time=p.open_time[:n], close_time=p.close_time[:n], log_close=p.log_close[:n],
                               log_open=p.log_open[:n], mask=f(p.mask), log_high=f(p.log_high), log_low=f(p.log_low))


def with_highs_lows(p: Panel) -> Panel:
    """Synthetic bars have no range; give them a modest one so brackets can be tested."""
    rng = np.random.default_rng(1)
    hi = np.maximum(p.log_open, p.log_close) + np.abs(rng.standard_normal(p.log_close.shape)) * 0.004
    lo = np.minimum(p.log_open, p.log_close) - np.abs(rng.standard_normal(p.log_close.shape)) * 0.004
    return dataclasses.replace(p, log_high=hi, log_low=lo)


class Sim:
    def __init__(self, tmp: Path, *, kind="paper", phi=0.10, n_bars=320, k0=200, seed=5, capital=100_000.0,
                 risk: dict | None = None, live: dict | None = None, book: dict | None = None,
                 broker=None, n_assets=N_ASSETS, require_approval=False):
        self.panel = with_highs_lows(generate_panel(n_bars, n_assets, bar="1d", seed=seed, phi_idio=phi,
                                                    start_price=100.0))
        self.k = k0
        self.tmp = tmp
        (tmp / "config").mkdir(parents=True, exist_ok=True)
        (tmp / "config" / "run.yaml").write_text(yaml.safe_dump({
            "name": "sim", "data": {"source": "equity", "bar": "1d"},
            "cross_section": {"enabled": True, "symbols": self.panel.symbols, "residualise": "beta",
                              "min_names_per_bar": 5},
            "forecast": {"forecaster": "ar1", "context_len": 128, "horizon": 1},
            "costs": {"commission_bps": 0.2, "half_spread_bps": 0.8, "slippage_bps": 0.5}}))
        self.cfg = BotConfig(
            name="sim", run_config="config/run.yaml", capital=capital,
            risk=RiskConfig(**{"max_capital": capital, **(risk or {})}),
            book=BookConfig(**{"top_fraction": 0.2, "gross": 1.0, "max_name_weight": 0.05, "min_trade_weight": 0.002,
                               **(book or {})}),
            broker=BrokerConfig(kind=kind), live=LiveGuard(require_approval=require_approval, **(live or {})),
            smoothing_halflife=3.0, score_warmup_days=6, base_dir=str(tmp))
        self.t = self.evening()
        store = Store(":memory:")
        if broker is None and kind != "paper":
            # a stand-in so live/alpaca CONFIGS can be exercised without credentials or a network
            from tfm_edge.config import CostModel
            from tfm_edge.execution.broker import PaperBroker
            broker = PaperBroker(store, capital, CostModel(0.2, 0.8, 0.5), now_fn=lambda: self.t)
        self.ctx: Context = build_context(
            self.cfg, env={}, now=lambda: self.t, broker=broker, calendar=EveryDayCalendar(),
            load_panel=lambda: slice_panel(self.panel, self.k), store=store)

    # time helpers: the evening a bar is published, and the next morning before the open
    def evening(self, k: int | None = None) -> datetime:
        d = self.day(self.k if k is None else k)
        return datetime.combine(d, time(17, 0), tzinfo=ET)

    def morning(self, k: int | None = None) -> datetime:
        d = self.day(self.k if k is None else k) + timedelta(days=1)
        return datetime.combine(d, time(9, 0), tzinfo=ET)

    def day(self, k: int) -> date:
        return date.fromisoformat(str(np.datetime_as_string(self.panel.open_time[k], unit="D")))

    def at(self, t: datetime) -> "Sim":
        self.t = t
        return self

    def day_cycle(self, approve_pending=True):
        """One full evening-to-morning cycle. Returns (plan, execute_result)."""
        from tfm_edge.execution import engine
        self.at(self.evening())
        pl = engine.plan(self.ctx)
        if pl["status"] == "pending" and approve_pending:
            pl = engine.approve(self.ctx, pl["id"])
        self.at(self.morning())
        res = engine.execute(self.ctx)
        self.k += 1
        return pl, res
