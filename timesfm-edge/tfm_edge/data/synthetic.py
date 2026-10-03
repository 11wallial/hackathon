"""Synthetic bar generators with KNOWN answers, used to validate the harness itself.

If the harness reports an edge on `random_walk`, the harness is broken (leak).
If the harness reports no edge on `ar1` with phi=0.15, the harness is broken (blind).
Real data is only worth running once both of those pass.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import bar_timedelta, validate_bars


def _garch_vol(n: int, rng: np.random.Generator, omega=1e-7, alpha=0.08, beta=0.90, base_sigma=0.004) -> np.ndarray:
    """GARCH(1,1) conditional sigma path, unconditional sigma ~ base_sigma."""
    omega = base_sigma**2 * (1 - alpha - beta)
    sig2 = np.empty(n)
    sig2[0] = base_sigma**2
    z = rng.standard_normal(n)
    eps = np.empty(n)
    eps[0] = np.sqrt(sig2[0]) * z[0]
    for t in range(1, n):
        sig2[t] = omega + alpha * eps[t - 1] ** 2 + beta * sig2[t - 1]
        eps[t] = np.sqrt(sig2[t]) * z[t]
    return np.sqrt(sig2), z


def generate(kind: str, n: int, bar: str = "1h", seed: int = 0, phi: float = 0.0,
             base_sigma: float = 0.004, start_price: float = 30000.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sigma, z = _garch_vol(n, rng, base_sigma=base_sigma)
    r = np.empty(n)
    if kind == "random_walk":
        r = sigma * z                       # martingale: true hit rate is exactly 0.5
    elif kind == "ar1":
        r[0] = sigma[0] * z[0]
        for t in range(1, n):
            r[t] = phi * r[t - 1] + sigma[t] * z[t]   # planted, knowable edge
    elif kind == "garch_only":
        r = sigma * z                       # same as random_walk; named for Test B experiments
    elif kind == "trend":
        drift = 0.3 * base_sigma            # constant drift: always-long 'edge', not a forecasting edge
        r = drift + sigma * z
    else:
        raise ValueError(kind)

    log_close = np.log(start_price) + np.cumsum(r)
    close = np.exp(log_close)
    # open = previous close plus a small gap so open != close (matters for open-to-open realised returns)
    gap = rng.standard_normal(n) * base_sigma * 0.1
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1] * np.exp(gap[1:])
    intrabar = np.abs(rng.standard_normal(n)) * sigma * 0.5
    high = np.maximum(open_, close) * np.exp(intrabar)
    low = np.minimum(open_, close) * np.exp(-intrabar)
    td = bar_timedelta(bar)
    t0 = pd.Timestamp("2022-01-01", tz="UTC")
    df = pd.DataFrame({
        "open_time": t0 + np.arange(n) * td,
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.lognormal(5, 0.5, n),
    })
    return validate_bars(df, bar)
