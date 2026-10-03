"""The decision function: a PURE function from (scores, current book, config, costs)
to a target book. No randomness, no clock, no I/O, no model call (hard constraint 3).

Same inputs always give the same output, which is what makes a live decision
reproducible after the fact and comparable to the backtest.

PARITY WITH THE BACKTEST
------------------------
The book is built the same way analysis/panel_run.py builds it: rank the
cross-sectional scores, long the top `top_fraction`, short the bottom, equal weight
within each side, dollar-neutral. With every name eligible and no caps binding,
`decide()` returns exactly what features.cross_section.cross_sectional_weights
returns; tests/test_decision.py asserts that. The live additions (eligibility,
name cap, no-trade band, forced exits) are the places live differs from the
backtest, and each is reported in Decision.notes so the divergence is visible.

WHY THE DEFAULT IS TO DO LITTLE
-------------------------------
A daily cross-sectional book dies on turnover, not on forecast quality. So the
function holds unless there is a reason to trade: positions inside the no-trade band
are left alone, and the whole book is only rebuilt every `rebalance_every` days.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from ..config import CostModel


@dataclass(frozen=True)
class BookConfig:
    top_fraction: float = 0.2         # long this fraction of the top, short this of the bottom
    gross: float = 1.0                # total |weight|, as a multiple of capital
    max_name_weight: float = 0.05     # per-name cap, as a fraction of capital
    min_trade_weight: float = 0.002   # no-trade band: ignore weight changes smaller than this
    rebalance_every: int = 1          # rebuild the book at most every N sessions
    # If set, a NEW position needs a model-forecast residual return of at least
    # (round-trip cost + this many bps) in the right direction. None disables it.
    # The Phase 1 sweep did not include this filter, so enabling it means live
    # behaviour differs from the backtested construction; Decision.notes says so.
    net_edge_threshold_bps: float | None = None


@dataclass(frozen=True)
class Decision:
    target: dict                       # symbol -> signed weight (fraction of capital); only non-zero names
    sides: dict                        # symbol -> "long" | "short" | "flat" for every name seen
    rebalanced: bool                   # False when held because of the cadence
    turnover: float                    # sum |target - current|, as a fraction of capital
    names_changed: int
    n_long: int
    n_short: int
    gross: float
    net: float
    notes: tuple = field(default_factory=tuple)

    def fraction_changed(self, universe_size: int) -> float:
        return self.names_changed / universe_size if universe_size else 0.0


def _k(n_valid: int, top_fraction: float) -> int:
    """Names per side. Same rule as cross_sectional_weights so the two agree."""
    k = max(1, int(round(top_fraction * n_valid)))
    if 2 * k > n_valid:
        k = n_valid // 2
    return k


def decide(scores: Mapping[str, float],
           current: Mapping[str, float],
           cfg: BookConfig,
           costs: CostModel,
           *,
           can_long: Iterable[str] | None = None,
           can_short: Iterable[str] | None = None,
           forecast_bps: Mapping[str, float] | None = None,
           sessions_since_rebalance: int = 10**9) -> Decision:
    """Return the target book.

    scores:   symbol -> cross-sectional score (higher = more bullish). Names with a
              missing or non-finite score are NOT in the tradable universe today and
              are exited if held (a name that dropped out of the index, lost its
              data, or stopped trading must not be carried on a stale view).
    current:  symbol -> signed weight now (fraction of capital).
    can_long / can_short: names the broker will let us open on that side. None means
              all. Shorting is the one that matters: hard-to-borrow names are skipped
              and the next-ranked name is used, which is a deviation from the backtest.
    forecast_bps: symbol -> model median residual return in bps; only used when
              cfg.net_edge_threshold_bps is set.
    sessions_since_rebalance: how long since the book was last rebuilt.
    """
    notes: list[str] = []
    valid = {s: float(v) for s, v in scores.items() if v is not None and math.isfinite(v)}
    cur = {s: float(w) for s, w in current.items() if abs(w) > 1e-12}

    # Names we hold but can no longer score are exited regardless of cadence.
    forced_exit = sorted(s for s in cur if s not in valid)
    if forced_exit:
        notes.append(f"forced exit (no score today): {', '.join(forced_exit)}")

    if sessions_since_rebalance < cfg.rebalance_every:
        target = {s: w for s, w in cur.items() if s in valid}
        notes.append(f"held: {sessions_since_rebalance} < rebalance_every={cfg.rebalance_every}")
        return _finish(target, cur, valid, cfg, rebalanced=False, notes=notes)

    long_ok = set(valid) if can_long is None else set(can_long) & set(valid)
    short_ok = set(valid) if can_short is None else set(can_short) & set(valid)

    # Optional net-of-cost edge filter, applied to NEW positions only.
    if cfg.net_edge_threshold_bps is not None and forecast_bps is not None:
        need = costs.round_trip_bps() + cfg.net_edge_threshold_bps
        dropped = 0
        for s in list(long_ok):
            if cur.get(s, 0.0) <= 0 and forecast_bps.get(s, float("-inf")) < need:
                long_ok.discard(s); dropped += 1
        for s in list(short_ok):
            if cur.get(s, 0.0) >= 0 and forecast_bps.get(s, float("inf")) > -need:
                short_ok.discard(s); dropped += 1
        notes.append(f"net-edge filter (>= {need:.1f} bps) removed {dropped} candidate entries; "
                     f"NOT part of the backtested construction")

    # Rank with a deterministic tie-break on the symbol.
    ranked = sorted(valid, key=lambda s: (valid[s], s))
    k = _k(len(valid), cfg.top_fraction)
    longs = [s for s in reversed(ranked) if s in long_ok][:k]
    shorts = [s for s in ranked if s in short_ok and s not in longs][:k]
    if len(longs) < k or len(shorts) < k:
        notes.append(f"eligibility shrank the book: {len(longs)} long / {len(shorts)} short of {k} per side")

    target: dict = {}
    half = cfg.gross / 2.0
    for side_names, sign in ((longs, 1.0), (shorts, -1.0)):
        if not side_names:
            continue
        w = half / len(side_names)
        capped = min(w, cfg.max_name_weight)
        if capped < w - 1e-12:
            notes.append(f"name cap {cfg.max_name_weight:.3f} bound on the {'long' if sign > 0 else 'short'} side "
                         f"(wanted {w:.3f}); gross is lower than configured")
        for s in side_names:
            target[s] = sign * capped

    return _finish(target, cur, valid, cfg, rebalanced=True, notes=notes)


def _finish(target: dict, cur: dict, valid: dict, cfg: BookConfig, *, rebalanced: bool,
            notes: list) -> Decision:
    # No-trade band: leave a position alone if the change is too small to be worth a trade.
    if cfg.min_trade_weight > 0:
        held = 0
        for s in sorted(set(target) | set(cur)):
            if s not in valid:
                continue                                  # forced exits are never suppressed
            before, after = cur.get(s, 0.0), target.get(s, 0.0)
            if 0 < abs(after - before) < cfg.min_trade_weight:
                if abs(before) > 1e-12:
                    target[s] = before
                else:
                    target.pop(s, None)
                held += 1
        if held:
            notes.append(f"no-trade band left {held} small changes alone")

    names = sorted(set(target) | set(cur))
    turnover = sum(abs(target.get(s, 0.0) - cur.get(s, 0.0)) for s in names)
    changed = sum(1 for s in names if abs(target.get(s, 0.0) - cur.get(s, 0.0)) > 1e-12)
    sides = {s: ("long" if target.get(s, 0.0) > 0 else "short" if target.get(s, 0.0) < 0 else "flat")
             for s in sorted(set(valid) | set(cur))}
    return Decision(
        target={s: w for s, w in target.items() if abs(w) > 1e-12},
        sides=sides, rebalanced=rebalanced, turnover=turnover, names_changed=changed,
        n_long=sum(1 for w in target.values() if w > 0),
        n_short=sum(1 for w in target.values() if w < 0),
        gross=sum(abs(w) for w in target.values()),
        net=sum(target.values()),
        notes=tuple(notes),
    )
