"""Entry brackets: a stop and a target, set at entry time.

BARRIER GEOMETRY, READ THIS BEFORE TUNING ANYTHING
--------------------------------------------------
For a driftless process, the probability of touching the target before the stop is
approximately

        P(target first) = SL / (SL + TP)

where SL and TP are the distances to the stop and target. So the WIN RATE of a bracketed
trade is set by the bracket ratio, not by the quality of the signal. A 3:1 stop-to-target
ratio "wins" about 75% of the time on pure noise. A high win rate carries no information
about edge, and optimising brackets for it will find a configuration that looks excellent
and earns nothing. Judge the strategy on net return per unit of risk, never on win rate.

WHAT THESE BRACKETS ARE FOR
---------------------------
They are disaster protection, set wide (default 3 daily standard deviations each way). They
are NOT part of the validated edge: the Phase 1 backtest held positions without stops, so a
stop that triggers is live behaviour the backtest did not model. The divergence report will
show it. A tight target in particular caps winners and will drag returns below the backtest.
"""
from __future__ import annotations

from dataclasses import dataclass

from .limits import RiskConfig


@dataclass(frozen=True)
class Bracket:
    side: str            # "long" | "short"
    entry: float
    stop: float
    target: float

    def barrier_win_probability(self) -> float:
        """Win probability implied by geometry alone for a driftless process."""
        return barrier_win_probability(abs(self.entry - self.stop), abs(self.target - self.entry))


def barrier_win_probability(stop_distance: float, target_distance: float) -> float:
    total = stop_distance + target_distance
    return stop_distance / total if total > 0 else 0.5


def make_bracket(entry: float, side: str, daily_sigma: float, cfg: RiskConfig) -> Bracket:
    """daily_sigma is the trailing standard deviation of daily simple returns."""
    if side not in ("long", "short"):
        raise ValueError(side)
    if not (entry > 0 and daily_sigma > 0):
        raise ValueError("entry and daily_sigma must be positive")
    sl = cfg.stop_vol_mult * daily_sigma
    tp = cfg.target_vol_mult * daily_sigma
    if side == "long":
        return Bracket("long", entry, stop=entry * (1.0 - sl), target=entry * (1.0 + tp))
    return Bracket("short", entry, stop=entry * (1.0 + sl), target=entry * (1.0 - tp))


def breached(bracket: Bracket, low: float, high: float) -> str | None:
    """Which barrier did a bar's range touch? If both, assume the stop first: pessimistic,
    because a daily bar cannot say which came first."""
    if bracket.side == "long":
        hit_stop, hit_tgt = low <= bracket.stop, high >= bracket.target
    else:
        hit_stop, hit_tgt = high >= bracket.stop, low <= bracket.target
    if hit_stop:
        return "stop"
    if hit_tgt:
        return "target"
    return None
