"""Risk limits. Pure functions: numbers in, a list of violations out.

Two severities:
  BLOCK  refuse this plan or order; the bot stays up and can plan again tomorrow
  HALT   stop trading and require a human to resume (the daily loss limit, drawdown)

The caller decides what to do with a violation. Nothing here touches a broker, so every
rule can be tested with plain numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

BLOCK, HALT = "block", "halt"


@dataclass(frozen=True)
class RiskConfig:
    max_capital: float                       # hard ceiling on capital the bot may deploy, in dollars
    max_gross_exposure: float = 1.10         # sum |position| / capital
    max_net_exposure: float = 0.10           # |sum signed position| / capital (dollar neutrality)
    max_name_weight: float = 0.06            # largest single |position| / capital
    max_order_notional: float | None = None  # per-order cap in dollars; None = capital * max_name_weight
    max_orders_per_day: int = 80
    max_turnover_per_day: float = 1.0        # sum |trade| / capital; a data error usually shows up here
    daily_loss_limit: float = 0.02           # halt if equity falls this fraction below the day's start
    max_drawdown_halt: float = 0.10          # halt if equity falls this fraction below its peak
    stop_vol_mult: float = 3.0               # stop distance in daily sigmas
    target_vol_mult: float = 3.0             # target distance in daily sigmas
    min_price: float = 2.0                   # do not trade sub-$2 stocks
    max_price_age_days: int = 5              # reference price older than this is stale
    flatten_on_halt: bool = False            # a halt cancels orders; True also closes every position


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule}: {self.detail}"


def check_account(equity: float, day_start_equity: float | None, peak_equity: float | None,
                  cfg: RiskConfig) -> list[Violation]:
    """Account-level limits. These HALT: a human has to look before trading resumes."""
    out: list[Violation] = []
    if day_start_equity and day_start_equity > 0:
        loss = (day_start_equity - equity) / day_start_equity
        if loss >= cfg.daily_loss_limit:
            out.append(Violation("daily_loss_limit", HALT,
                                 f"equity {equity:,.0f} is {loss:.2%} below the day's start "
                                 f"{day_start_equity:,.0f} (limit {cfg.daily_loss_limit:.2%})"))
    if peak_equity and peak_equity > 0:
        dd = (peak_equity - equity) / peak_equity
        if dd >= cfg.max_drawdown_halt:
            out.append(Violation("max_drawdown", HALT,
                                 f"drawdown {dd:.2%} from peak {peak_equity:,.0f} "
                                 f"(limit {cfg.max_drawdown_halt:.2%})"))
    return out


def check_plan(target_qty: Mapping[str, int], current_qty: Mapping[str, int],
               prices: Mapping[str, float], capital: float, cfg: RiskConfig) -> list[Violation]:
    """Limits on the portfolio a plan would leave behind. All BLOCK."""
    out: list[Violation] = []
    if capital <= 0:
        return [Violation("capital", BLOCK, f"capital {capital} is not positive")]
    if capital > cfg.max_capital + 1e-9:
        out.append(Violation("max_capital", BLOCK,
                             f"capital {capital:,.0f} exceeds the hard ceiling {cfg.max_capital:,.0f}"))

    missing = sorted(s for s in set(target_qty) | set(current_qty)
                     if (target_qty.get(s, 0) or current_qty.get(s, 0)) and not (prices.get(s, 0) > 0))
    if missing:
        out.append(Violation("price_missing", BLOCK, f"no usable price for {', '.join(missing[:8])}"))
        return out

    notional = {s: target_qty.get(s, 0) * prices[s] for s in target_qty if target_qty.get(s, 0)}
    gross = sum(abs(v) for v in notional.values()) / capital
    net = sum(notional.values()) / capital
    if gross > cfg.max_gross_exposure + 1e-9:
        out.append(Violation("max_gross_exposure", BLOCK, f"gross {gross:.3f} > {cfg.max_gross_exposure:.3f}"))
    if abs(net) > cfg.max_net_exposure + 1e-9:
        out.append(Violation("max_net_exposure", BLOCK, f"net {net:+.3f} outside +/-{cfg.max_net_exposure:.3f}"))
    for s, v in sorted(notional.items()):
        if abs(v) / capital > cfg.max_name_weight + 1e-9:
            out.append(Violation("max_name_weight", BLOCK,
                                 f"{s} is {abs(v) / capital:.3f} of capital > {cfg.max_name_weight:.3f}"))
        if prices[s] < cfg.min_price:
            out.append(Violation("min_price", BLOCK, f"{s} trades at {prices[s]:.2f} < {cfg.min_price:.2f}"))

    order_cap = cfg.max_order_notional if cfg.max_order_notional is not None else capital * cfg.max_name_weight * 2
    trades = {s: target_qty.get(s, 0) - current_qty.get(s, 0)
              for s in set(target_qty) | set(current_qty)}
    trades = {s: q for s, q in trades.items() if q}
    if len(trades) > cfg.max_orders_per_day:
        out.append(Violation("max_orders_per_day", BLOCK, f"{len(trades)} orders > {cfg.max_orders_per_day}"))
    turnover = sum(abs(q) * prices[s] for s, q in trades.items()) / capital
    if turnover > cfg.max_turnover_per_day + 1e-9:
        out.append(Violation("max_turnover_per_day", BLOCK,
                             f"turnover {turnover:.3f} > {cfg.max_turnover_per_day:.3f}; this usually "
                             f"means bad data, not a real signal"))
    for s, q in sorted(trades.items()):
        if abs(q) * prices[s] > order_cap + 1e-9:
            out.append(Violation("max_order_notional", BLOCK,
                                 f"{s} order {abs(q) * prices[s]:,.0f} > {order_cap:,.0f}"))
    return out


def has_halt(violations: list[Violation]) -> bool:
    return any(v.severity == HALT for v in violations)
