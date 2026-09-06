"""Multi-asset panels.

A panel is an aligned (n_bars, n_assets) matrix of log closes plus log opens, with one
shared time index. Everything cross-sectional is built on this.

The synthetic generator plants predictability ONLY in the idiosyncratic component, with
an unpredictable common market factor on top. That is the honest hard case: a univariate
forecaster fed the raw series has its signal diluted by the market factor, and the
residualisation step in features/cross_section.py is what recovers it. If residualising
did not help here, the idea would be wrong.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .bars import bar_timedelta


@dataclass(frozen=True)
class Panel:
    open_time: np.ndarray        # (n_bars,) datetime64
    close_time: np.ndarray
    log_close: np.ndarray        # (n_bars, n_assets)
    log_open: np.ndarray         # (n_bars, n_assets)
    symbols: list[str]
    bar: str

    @property
    def n_bars(self) -> int:
        return self.log_close.shape[0]

    @property
    def n_assets(self) -> int:
        return self.log_close.shape[1]

    def returns(self) -> np.ndarray:
        """(n_bars, n_assets) one-bar log returns; row 0 is NaN."""
        r = np.full_like(self.log_close, np.nan)
        r[1:] = np.diff(self.log_close, axis=0)
        return r


def _garch_path(n: int, rng: np.random.Generator, base_sigma: float,
                alpha: float = 0.08, beta: float = 0.90) -> np.ndarray:
    omega = base_sigma ** 2 * (1 - alpha - beta)
    sig2 = np.empty(n)
    sig2[0] = base_sigma ** 2
    eps = np.empty(n)
    z = rng.standard_normal(n)
    eps[0] = np.sqrt(sig2[0]) * z[0]
    for t in range(1, n):
        sig2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sig2[t - 1]
        eps[t] = np.sqrt(sig2[t]) * z[t]
    return np.sqrt(sig2)


def generate_panel(n_bars: int, n_assets: int, bar: str = "1d", seed: int = 0,
                   phi_idio: float = 0.0, market_vol: float = 0.020,
                   idio_vol: float = 0.030, beta_spread: float = 0.35,
                   start_price: float = 100.0) -> Panel:
    """Synthetic panel.

    phi_idio: AR(1) coefficient on the IDIOSYNCRATIC return only. 0 means no edge
        anywhere (leak detector). Positive means a purely cross-sectional, purely
        market-neutral edge exists (power detector).
    market_vol / idio_vol: per-bar standard deviations. Defaults give the market roughly
        a third of total variance at beta 1, which is close to a liquid crypto panel.
    """
    rng = np.random.default_rng(seed)
    m_sigma = _garch_path(n_bars, rng, market_vol)
    market = m_sigma * rng.standard_normal(n_bars)
    betas = 1.0 + beta_spread * rng.standard_normal(n_assets)

    idio = np.empty((n_bars, n_assets))
    e = rng.standard_normal((n_bars, n_assets)) * idio_vol
    idio[0] = e[0]
    for t in range(1, n_bars):
        idio[t] = phi_idio * idio[t - 1] + e[t]

    r = market[:, None] * betas[None, :] + idio
    log_close = np.log(start_price) + np.cumsum(r, axis=0)
    gap = rng.standard_normal((n_bars, n_assets)) * idio_vol * 0.1
    log_open = np.empty_like(log_close)
    log_open[0] = np.log(start_price)
    log_open[1:] = log_close[:-1] + gap[1:]

    td = bar_timedelta(bar)
    t0 = np.datetime64("2021-01-01T00:00:00", "ns")
    open_time = t0 + np.arange(n_bars) * td.to_timedelta64()
    return Panel(open_time=open_time, close_time=open_time + td.to_timedelta64(),
                 log_close=log_close, log_open=log_open,
                 symbols=[f"SYN{i:03d}" for i in range(n_assets)], bar=bar)


def panel_from_frames(frames: dict[str, pd.DataFrame], bar: str) -> Panel:
    """Align validated bar frames on their shared timestamps. Assets are dropped if they
    do not cover the full intersection; a panel with ragged history silently changes its
    own cross-section over time, which looks exactly like alpha."""
    idx = None
    for df in frames.values():
        s = set(df["open_time"].to_numpy())
        idx = s if idx is None else (idx & s)
    times = np.array(sorted(idx))
    if len(times) < 100:
        raise ValueError(f"only {len(times)} shared bars across {len(frames)} assets")
    syms = sorted(frames)
    lc = np.column_stack([np.log(frames[s].set_index("open_time").loc[times, "close"].to_numpy()) for s in syms])
    lo = np.column_stack([np.log(frames[s].set_index("open_time").loc[times, "open"].to_numpy()) for s in syms])
    return Panel(open_time=times, close_time=times + bar_timedelta(bar).to_timedelta64(),
                 log_close=lc, log_open=lo, symbols=syms, bar=bar)
