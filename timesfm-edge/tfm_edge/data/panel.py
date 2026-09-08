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
    # (n_bars, n_assets) bool: was this name a tradable member of the universe at this
    # bar? None means "always, everywhere", which is only honest for a universe that
    # genuinely never changed. For equities it never is: names list, delist, get
    # acquired and drop out of the index, and a panel that ignores that is a list of
    # survivors, which is the single largest source of fake alpha in equity research.
    mask: np.ndarray | None = None

    @property
    def n_bars(self) -> int:
        return self.log_close.shape[0]

    @property
    def n_assets(self) -> int:
        return self.log_close.shape[1]

    def membership(self) -> np.ndarray:
        if self.mask is None:
            return np.isfinite(self.log_close)
        return self.mask & np.isfinite(self.log_close)

    def returns(self) -> np.ndarray:
        """(n_bars, n_assets) one-bar log returns, NaN wherever the return is not both
        knowable and tradable: the first bar, and any bar whose previous bar was outside
        this name's membership."""
        r = np.full(self.log_close.shape, np.nan)
        r[1:] = np.diff(self.log_close, axis=0)
        m = self.membership()
        valid = np.zeros_like(m)
        valid[1:] = m[1:] & m[:-1]
        return np.where(valid, r, np.nan)

    def survivorship_report(self) -> dict:
        """How much does this panel's cross-section change over time? A universe that is
        identical on the first and last bar is a list of survivors."""
        m = self.membership()
        first, last = m[0].sum(), m[-1].sum()
        return {
            "n_assets": self.n_assets,
            "members_first_bar": int(first),
            "members_last_bar": int(last),
            "members_every_bar": int(m.all(axis=0).sum()),
            "mean_members": float(m.sum(axis=1).mean()),
            "static_universe": bool(m.all()),
        }


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
    """Align validated bar frames on the timestamps every asset shares.

    Bars outside the intersection are dropped rather than filled: a panel whose
    cross-section silently changes size over time looks exactly like alpha, because the
    names that drop out are the ones that stopped trading.

    Timestamps come back tz-naive UTC to match the synthetic generator. Frames carry
    tz-aware timestamps, whose .to_numpy() is an object array of Timestamps, so the
    conversion has to be explicit or every later datetime arithmetic fails.
    """
    idx = None
    for df in frames.values():
        i = pd.DatetimeIndex(df["open_time"])
        idx = i if idx is None else idx.intersection(i)
    idx = idx.sort_values()
    if len(idx) < 100:
        raise ValueError(f"only {len(idx)} shared bars across {len(frames)} assets")
    syms = sorted(frames)
    lc = np.column_stack([np.log(frames[s].set_index("open_time").loc[idx, "close"].to_numpy(float)) for s in syms])
    lo = np.column_stack([np.log(frames[s].set_index("open_time").loc[idx, "open"].to_numpy(float)) for s in syms])
    naive = idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx
    times = naive.to_numpy(dtype="datetime64[ns]")
    return Panel(open_time=times, close_time=times + bar_timedelta(bar).to_timedelta64(),
                 log_close=lc, log_open=lo, symbols=syms, bar=bar)
