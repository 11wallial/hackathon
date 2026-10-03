"""Load bars from a CSV with columns open_time,open,high,low,close,volume.

open_time must be the bar's START (ISO8601 or epoch ms). If your file stores the
bar close time, pass close_time_column=True and it is shifted back by one bar.
"""
from __future__ import annotations

import pandas as pd

from .bars import bar_timedelta, validate_bars


def load_csv(path: str, bar: str, close_time_column: bool = False) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    ren = {}
    for want, alts in {
        "open_time": ["open_time", "timestamp", "time", "date", "datetime"],
        "open": ["open"], "high": ["high"], "low": ["low"], "close": ["close"], "volume": ["volume", "vol"],
    }.items():
        for a in alts:
            if a in cols:
                ren[cols[a]] = want
                break
    df = df.rename(columns=ren)
    if pd.api.types.is_numeric_dtype(df["open_time"]):
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    else:
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    if close_time_column:
        df["open_time"] = df["open_time"] - bar_timedelta(bar)
    if "volume" not in df:
        df["volume"] = 0.0
    return validate_bars(df, bar)
