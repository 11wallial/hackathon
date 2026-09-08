"""Bar schema and point-in-time discipline.

A bar with `open_time` T and `close_time` T+bar is NOT knowable until close_time.
Everything downstream keys on `knowable_at` = close_time, never on open_time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED = ["open_time", "open", "high", "low", "close", "volume"]

BAR_TO_TIMEDELTA = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D",
}


def bar_timedelta(bar: str) -> pd.Timedelta:
    if bar not in BAR_TO_TIMEDELTA:
        raise ValueError(f"unsupported bar {bar}; add it to BAR_TO_TIMEDELTA")
    return pd.Timedelta(BAR_TO_TIMEDELTA[bar])


def validate_bars(df: pd.DataFrame, bar: str) -> pd.DataFrame:
    """Enforce schema, monotone time, no duplicates, no gaps, positive prices.

    Gaps are an error rather than silently forward-filled: a filled gap creates a
    bar whose 'return' is zero and whose 'volatility' is fake, which flatters
    calibration metrics. If your venue has gaps, drop them upstream explicitly.
    """
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"bars missing columns {missing}")
    df = df.copy()
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df = df.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    td = bar_timedelta(bar)
    diffs = df["open_time"].diff().dropna()
    bad = diffs[diffs != td]
    if len(bad):
        raise ValueError(f"{len(bad)} gaps/irregular intervals in bars, first at {bad.index[0]}: {bad.iloc[0]}")
    for c in ["open", "high", "low", "close"]:
        if (df[c] <= 0).any() or df[c].isna().any():
            raise ValueError(f"non-positive or NaN in {c}")
    df["close_time"] = df["open_time"] + td
    df["knowable_at"] = df["close_time"]  # the bar exists only once it has closed
    return df[REQUIRED + ["close_time", "knowable_at"]]


def log_close(df: pd.DataFrame) -> np.ndarray:
    return np.log(df["close"].to_numpy(dtype=np.float64))
