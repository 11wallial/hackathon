"""Cross-sectional features, targets and portfolio construction.

WHY CROSS-SECTIONAL IS THE LEVER
--------------------------------
Two independent gains, both large:

1. The common market factor is the least predictable and most volatile part of any
   equity or crypto return. A dollar-neutral book removes it from the TARGET, so the
   volatility your edge has to overcome falls to the residual, while the cost per unit
   of notional is unchanged. Removing it from the INPUT as well (residualisation below)
   stops it from drowning the signal the model is trying to read.

2. Breadth. Sharpe scales as IC x sqrt(independent bets). Trading 60 names is worth far
   more than one, and it shortens the track record needed to prove the edge is real from
   decades to years. That second effect is what makes the result knowable at all.

RESIDUALISATION AND LOOK-AHEAD
------------------------------
Betas are estimated on the training fold only and held fixed through the test block. The
cross-sectional mean used to neutralise bar t uses only bar t's returns, which are
knowable at t's close. Neither step reaches forward.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..data.panel import Panel


@dataclass(frozen=True)
class PanelSamples:
    t: np.ndarray            # (n_times,) decision bar indices
    y_cc: np.ndarray         # (n_times, n_assets) close-to-close forecast target
    y_oo: np.ndarray         # (n_times, n_assets) open-to-open tradable return
    decision_at: np.ndarray
    horizon: int

    def __len__(self) -> int:
        return len(self.t)


def build_panel_samples(panel: Panel, horizon: int, context_len: int) -> PanelSamples:
    lc, lo = panel.log_close, panel.log_open
    n = panel.n_bars
    first = max(context_len - 1, 1)
    last = n - 2 - horizon
    if last < first:
        raise ValueError("not enough bars for this context_len/horizon")
    t = np.arange(first, last + 1)
    return PanelSamples(
        t=t,
        y_cc=lc[t + horizon] - lc[t],
        y_oo=lo[t + 1 + horizon] - lo[t + 1],
        decision_at=panel.close_time[t],
        horizon=horizon,
    )


def market_return(returns: np.ndarray) -> np.ndarray:
    """Equal-weighted mean across whoever is present at each bar. Names outside the
    universe carry NaN and are simply absent from that bar's average."""
    finite = np.isfinite(returns)
    n = finite.sum(axis=1)
    total = np.where(finite, returns, 0.0).sum(axis=1)
    return np.divide(total, n, out=np.zeros(len(returns)), where=n > 0)


def estimate_betas(returns: np.ndarray, end: int, min_obs: int = 60) -> np.ndarray:
    """OLS beta of each asset on the equal-weighted market, using bars [1, end) only.

    Fitted per asset over the bars where that asset was present, so a name with three
    years of history is not penalised for the years before it listed. Names with too
    little overlap fall back to 1.0 rather than to a beta estimated from noise."""
    r = returns[1:end]
    if r.size == 0:
        return np.ones(returns.shape[1])
    mkt = market_return(r)
    out = np.ones(r.shape[1])
    for i in range(r.shape[1]):
        ok = np.isfinite(r[:, i])
        if ok.sum() < min_obs:
            continue
        x, y = mkt[ok], r[ok, i]
        var = x.var()
        if var <= 0:
            continue
        out[i] = np.clip(np.cov(x, y, bias=True)[0, 1] / var, 0.0, 3.0)
    return out


def residual_log_close(panel: Panel, betas: np.ndarray, mode: str = "beta") -> np.ndarray:
    """Cumulative residual log price, the series fed to the forecaster.

    mode="none"   raw log close
    mode="demean" subtract the equal-weighted cross-sectional mean return each bar
    mode="beta"   subtract beta_i x market return each bar

    The cumulative sum starts at zero for every asset, which is what a level-input
    foundation model should see: a series whose trend is the asset's own drift relative
    to the market rather than the market's.
    """
    if mode == "none":
        return np.where(panel.membership(), panel.log_close, np.nan)
    r = panel.returns()
    mkt = market_return(r)
    resid = np.nan_to_num(r, nan=0.0) - mkt[:, None] * (betas[None, :] if mode == "beta" else 1.0)
    # Non-member bars contribute zero so the level stays continuous across a gap, then
    # are blanked out: the forecaster must never see a flat-lined stretch where a name
    # was not trading, and never gets a window from before it entered the universe.
    series = np.cumsum(np.where(np.isfinite(r) | (np.arange(len(r))[:, None] == 0), resid, 0.0), axis=0)
    return np.where(panel.membership(), series, np.nan)


def neutralise_targets(y: np.ndarray, betas: np.ndarray, mode: str = "beta") -> np.ndarray:
    """Remove the market component from the realised target the same way."""
    if mode == "none":
        return y
    mkt = market_return(y)
    return y - mkt[:, None] * (betas[None, :] if mode == "beta" else 1.0)


def cross_sectional_weights(scores: np.ndarray, top_fraction: float = 0.2,
                            gross: float = 1.0, use_ranks: bool = True) -> np.ndarray:
    """Dollar-neutral weights from one bar's cross-section of forecasts.

    Long the top `top_fraction`, short the bottom, equal weight within each side, total
    absolute exposure `gross`. Ranks rather than raw values because a single extreme
    forecast should not become the whole book.
    """
    s = np.asarray(scores, dtype=float)
    n = len(s)
    k = max(1, int(round(top_fraction * n)))
    if 2 * k > n:
        k = n // 2
    w = np.zeros(n)
    valid = np.isfinite(s)
    if valid.sum() < 2 * k:
        return w
    vals = np.where(valid, s, np.nan)
    order = np.argsort(np.where(np.isnan(vals), -np.inf, vals))
    order = order[np.isfinite(vals[order])]
    longs, shorts = order[-k:], order[:k]
    w[longs] = gross / (2 * k)
    w[shorts] = -gross / (2 * k)
    return w


def build_book(scores: np.ndarray, top_fraction: float = 0.2, gross: float = 1.0) -> np.ndarray:
    """(n_times, n_assets) weight matrix from a (n_times, n_assets) score matrix."""
    return np.vstack([cross_sectional_weights(scores[i], top_fraction, gross) for i in range(scores.shape[0])])


def book_pnl(w: np.ndarray, y: np.ndarray, cost_rt_frac: float) -> tuple[np.ndarray, dict]:
    """Per-bar net return of the book, charging cost on |dw| at half a round trip per unit."""
    prev = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    turnover = np.abs(w - prev).sum(axis=1)
    gross = (w * y).sum(axis=1)
    cost = turnover * (cost_rt_frac / 2.0)
    net = gross - cost
    return net, {
        "mean_gross_bps": float(1e4 * gross.mean()),
        "mean_cost_bps": float(1e4 * cost.mean()),
        "mean_net_bps": float(1e4 * net.mean()),
        "turnover_per_bar": float(turnover.mean()),
        "avg_names_held": float((w != 0).sum(axis=1).mean()),
    }
