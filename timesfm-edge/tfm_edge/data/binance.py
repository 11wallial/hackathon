"""Binance public klines loader with a parquet cache. No API key needed.

market="um": USDS-M perpetual futures (https://fapi.binance.com)
market="spot": spot (https://api.binance.com)
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

from .bars import bar_timedelta, validate_bars

_BASE = {"um": "https://fapi.binance.com/fapi/v1/klines", "spot": "https://api.binance.com/api/v3/klines"}
_LIMIT = 1000


def fetch_klines(symbol: str, bar: str, years: float, market: str = "um",
                 cache_dir: str = "cache/data", session: requests.Session | None = None) -> pd.DataFrame:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"binance_{market}_{symbol}_{bar}.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        return validate_bars(df, bar)

    url = _BASE[market]
    sess = session or requests.Session()
    td = bar_timedelta(bar)
    end = pd.Timestamp.utcnow().floor(td)
    start = end - pd.Timedelta(days=365.25 * years)
    rows: list[list] = []
    cur = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    while cur < end_ms:
        r = sess.get(url, params={"symbol": symbol, "interval": bar, "startTime": cur, "limit": _LIMIT}, timeout=30)
        if r.status_code == 429:
            time.sleep(5)
            continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = batch[-1][0] + int(td.total_seconds() * 1000)
        time.sleep(0.15)  # stay well inside the public rate limit
    if not rows:
        raise RuntimeError("Binance returned no klines")
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["open_time", "open", "high", "low", "close", "volume"]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    # drop the still-open last bar: it is not knowable yet
    df = df[df["open_time"] + td <= end]
    df = validate_bars(df, bar)
    df.to_parquet(path, index=False)
    return df
