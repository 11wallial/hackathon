"""From bars to today's scores.

This reuses the backtest's own functions for the cross-sectional z-score and the EWMA
smoothing (analysis.panel_run), the same beta residualisation (features.cross_section) and
the same forecaster factory. That is deliberate: the less code live shares with the backtest,
the more room there is for the two to disagree without anyone noticing.

REPRODUCIBILITY
---------------
The smoothed score for today is recomputed from the last `score_warmup_days` sessions of bars
every time, rather than carried forward as running state. So there is no hidden state that can
drift, a restart changes nothing, and the same bars always give the same score. The cost is
forecasting a few extra days; the forecaster's content-addressed cache makes repeats free.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..analysis.panel_run import MIN_CONTEXT, cross_sectional_scores, smooth_scores
from ..data.panel import Panel
from ..features.cross_section import estimate_betas, residual_log_close


@dataclass
class Signals:
    asof: str                                   # ISO date of the last bar
    n_configured: int
    coverage: float                             # fraction of configured symbols with a bar on asof
    scores: dict = field(default_factory=dict)  # symbol -> smoothed cross-sectional score (tradable names only)
    raw: dict = field(default_factory=dict)     # symbol -> today's unsmoothed z-score
    forecast_bps: dict = field(default_factory=dict)    # symbol -> model median residual return, bps
    quantiles: dict = field(default_factory=dict)       # symbol -> the nine quantiles, log-return units
    prices: dict = field(default_factory=dict)  # symbol -> last close
    sigma: dict = field(default_factory=dict)   # symbol -> trailing std of daily simple returns
    highs_lows: dict = field(default_factory=dict)
    model: str = ""
    notes: list = field(default_factory=list)


def asof_date(panel: Panel) -> str:
    return str(np.datetime_as_string(panel.open_time[-1], unit="D"))


def compute_signals(panel: Panel, *, forecaster, context_len: int, horizon: int, residualise: str,
                    smoothing_halflife: float, warmup_days: int, beta_window: int, vol_window: int,
                    n_configured: int) -> Signals:
    n = panel.n_bars
    t = n - 1
    member = panel.membership()
    asof = asof_date(panel)
    covered = int(member[t].sum())
    sig = Signals(asof=asof, n_configured=n_configured, coverage=covered / max(n_configured, 1),
                  model=getattr(forecaster, "version", getattr(forecaster, "name", "?")))

    rets = panel.returns()
    sub = rets[max(0, n - beta_window):]
    betas = estimate_betas(sub, len(sub))
    series = residual_log_close(panel, betas, residualise)

    # baselines fit on history; zero-shot models ignore this
    train = np.diff(series[:t], axis=0).ravel(order="F")
    forecaster.fit(train[np.isfinite(train)])

    first = max(1, t - warmup_days)
    days = list(range(first, t + 1))
    windows, slots = [], []
    for di, d in enumerate(days):
        for a in range(panel.n_assets):
            if not member[d, a]:
                continue
            w = series[max(0, d - context_len + 1):d + 1, a]
            w = w[np.isfinite(w)]
            if len(w) >= MIN_CONTEXT:
                windows.append(w)
                slots.append((di, a))
    if not windows:
        sig.notes.append("no forecastable names")
        return sig

    dist = forecaster.predict(windows, horizon).sorted()
    raw = np.full((len(days), panel.n_assets), np.nan)
    for (di, a), p in zip(slots, dist.point):
        raw[di, a] = p
    z = cross_sectional_scores(raw)
    smoothed = smooth_scores(z, smoothing_halflife)

    for (di, a), p, q in zip(slots, dist.point, dist.quantiles):
        if di != len(days) - 1:
            continue
        s = panel.symbols[a]
        sig.forecast_bps[s] = float(p) * 1e4
        sig.quantiles[s] = [float(x) for x in q]
    for a, s in enumerate(panel.symbols):
        if not member[t, a]:
            continue
        sig.prices[s] = float(np.exp(panel.log_close[t, a]))
        if panel.log_high is not None and np.isfinite(panel.log_high[t, a]):
            sig.highs_lows[s] = (float(np.exp(panel.log_high[t, a])), float(np.exp(panel.log_low[t, a])))
        if np.isfinite(z[-1, a]) and np.isfinite(smoothed[-1, a]):
            sig.raw[s] = float(z[-1, a])
            sig.scores[s] = float(smoothed[-1, a])
        c = np.exp(panel.log_close[max(0, t - vol_window):t + 1, a])
        r = np.diff(c) / c[:-1]
        r = r[np.isfinite(r)]
        if len(r) >= 20:
            sig.sigma[s] = float(np.std(r, ddof=1))
    return sig
