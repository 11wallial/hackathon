"""US equity daily bars, keyless, cached, with a point-in-time universe.

WHY EQUITIES
------------
The feasibility survey says a US equity cross-section is the only setup that clears both
hurdles at once: round-trip cost is about 3 bps against ~157 bps of daily residual move
(k = 0.019, break-even 0.512), and twenty years of history is enough to distinguish a
Sharpe near 1 from luck. Crypto perpetuals clear the cost hurdle at daily bars but only
offer four years, which is not enough to prove anything at a plausible edge.

TWO THINGS THAT WILL RUIN AN EQUITY BACKTEST
--------------------------------------------
1. **Corporate actions.** A 2-for-1 split shows up in raw closes as a -50% return. One
   such print in a cross-sectional book is a fake 50% move that dominates every real
   signal. Both loaders here return SPLIT- AND DIVIDEND-ADJUSTED prices, and the loader
   refuses a series containing a move so large it is almost certainly an unadjusted
   action (see MAX_ABS_DAILY_LOG_RETURN).
2. **Survivorship.** A list of today's index members, run backwards twenty years, is a
   list of companies that survived. Their past returns are conditioned on not going to
   zero. This is the largest source of fake alpha in equity research and it is easy to
   commit by accident. Supply a point-in-time membership file (see load_universe) and
   the panel will only hold a name while it was actually a member. Without one the
   loader still runs but the report carries a loud warning, because a static universe
   is a claim about the world that is almost never true.

SOURCES (both keyless)
----------------------
stooq : https://stooq.com/q/d/l/?s=aapl.us&i=d  plain CSV, adjusted, long history
yahoo : https://query1.finance.yahoo.com/v8/finance/chart/AAPL  JSON, has adjclose

A note on adjusted prices: the adjustment factor for a past bar is restated whenever a
new split or dividend happens, so today's adjusted series is not what a trader saw back
then. For RETURNS this is the correct choice anyway (the adjusted series gives the true
total return across the event, the raw series gives a fictional one), but it does mean
the price LEVELS fed to the model are not point-in-time. Since the model is fed a
residual series that is normalised anyway, this is the right trade; it is recorded here
so nobody discovers it later and calls it a bug.
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .bars import validate_bars
from .panel import Panel

STOOQ_URL = "https://stooq.com/q/d/l/"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

# A single-day move larger than this in a supposedly adjusted series almost always means
# an unhandled split rather than a real price move. log(2) = 0.69 is a 2:1 split.
MAX_ABS_DAILY_LOG_RETURN = 0.60


class UnadjustedPriceError(ValueError):
    """Raised when a series looks like it still contains raw corporate actions."""


def _check_adjusted(df: pd.DataFrame, symbol: str) -> None:
    r = np.diff(np.log(df["close"].to_numpy(float)))
    if len(r) and np.nanmax(np.abs(r)) > MAX_ABS_DAILY_LOG_RETURN:
        i = int(np.nanargmax(np.abs(r)))
        raise UnadjustedPriceError(
            f"{symbol}: {np.exp(r[i]) - 1:+.1%} single-day move on "
            f"{df['open_time'].iloc[i + 1].date()}. That is almost certainly an "
            f"unadjusted split or a bad print, not a return. Refusing to use this series."
        )


def fetch_stooq(symbol: str, session: requests.Session | None = None) -> pd.DataFrame:
    sess = session or requests.Session()
    r = sess.get(STOOQ_URL, params={"s": f"{symbol.lower()}.us", "i": "d"}, timeout=30)
    r.raise_for_status()
    if "Date" not in r.text[:200]:
        raise ValueError(f"stooq returned no data for {symbol}: {r.text[:120]!r}")
    df = pd.read_csv(io.StringIO(r.text))
    df = df.rename(columns={"Date": "open_time", "Open": "open", "High": "high",
                            "Low": "low", "Close": "close", "Volume": "volume"})
    return df[["open_time", "open", "high", "low", "close", "volume"]]


def fetch_yahoo(symbol: str, years: float, session: requests.Session | None = None) -> pd.DataFrame:
    sess = session or requests.Session()
    end = int(time.time())
    start = end - int(365.25 * 24 * 3600 * years)
    r = sess.get(f"{YAHOO_URL}{symbol}",
                 params={"period1": start, "period2": end, "interval": "1d", "events": "div,split"},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
    close = np.asarray(q["close"], dtype=float)
    df = pd.DataFrame({
        "open_time": pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_localize(None).normalize(),
        "open": np.asarray(q["open"], float), "high": np.asarray(q["high"], float),
        "low": np.asarray(q["low"], float), "close": close,
        "volume": np.asarray(q["volume"], float),
    })
    if adj is not None:
        # scale the whole bar by the close's adjustment factor so open/high/low stay
        # consistent with the adjusted close; execution happens at the adjusted open
        f = np.asarray(adj, float) / np.where(close > 0, close, np.nan)
        for c in ("open", "high", "low", "close"):
            df[c] = df[c] * f
    return df.dropna(subset=["open", "close"]).reset_index(drop=True)


def fetch_equity_bars(symbol: str, source: str = "stooq", years: float = 20.0,
                      cache_dir: str = "cache/data", session: requests.Session | None = None) -> pd.DataFrame:
    """One symbol's adjusted daily bars, cached as parquet.

    Bars are NOT gap-validated the way crypto bars are: equity markets are closed at
    weekends and on holidays, so a calendar gap is normal rather than a data fault. The
    panel aligns on trading days instead.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"equity_{source}_{symbol.upper()}_1d.parquet"
    if path.exists():
        return pd.read_parquet(path)
    df = fetch_stooq(symbol, session) if source == "stooq" else fetch_yahoo(symbol, years, session)
    df["open_time"] = pd.to_datetime(df["open_time"]).dt.tz_localize(None).dt.normalize()
    df = df.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)].reset_index(drop=True)
    if years:
        df = df[df["open_time"] >= pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=365.25 * years)]
    df = df.reset_index(drop=True)
    if len(df) < 250:
        raise ValueError(f"{symbol}: only {len(df)} daily bars, not enough to fold")
    _check_adjusted(df, symbol)
    df.to_parquet(path, index=False)
    return df


def load_universe(path: str | None) -> pd.DataFrame | None:
    """Point-in-time index membership: CSV with columns symbol,start_date,end_date.

    end_date blank means "still a member". One row per membership spell, so a name that
    left and rejoined gets two rows. Wikipedia's list of S&P 500 changes is enough to
    build one; so is any vendor's constituent history.
    """
    if not path:
        return None
    u = pd.read_csv(path)
    u.columns = [c.strip().lower() for c in u.columns]
    if "symbol" not in u:
        raise ValueError("universe file needs a 'symbol' column")
    for c in ("start_date", "end_date"):
        u[c] = pd.to_datetime(u[c], errors="coerce") if c in u else pd.NaT
    u["symbol"] = u["symbol"].str.upper().str.strip()
    return u


def build_membership(times: pd.DatetimeIndex, symbols: list[str],
                     universe: pd.DataFrame | None) -> np.ndarray:
    """(n_bars, n_assets) bool. All-True when no universe file is supplied, which is the
    survivorship-biased case the report warns about."""
    if universe is None:
        return np.ones((len(times), len(symbols)), dtype=bool)
    m = np.zeros((len(times), len(symbols)), dtype=bool)
    t = times.to_numpy()
    for j, sym in enumerate(symbols):
        for _, row in universe[universe["symbol"] == sym].iterrows():
            lo = np.datetime64(row["start_date"]) if pd.notna(row["start_date"]) else t[0]
            hi = np.datetime64(row["end_date"]) if pd.notna(row["end_date"]) else t[-1]
            m[:, j] |= (t >= lo) & (t <= hi)
    return m


def equity_panel(symbols: list[str], source: str = "stooq", years: float = 20.0,
                 cache_dir: str = "cache/data", universe_path: str | None = None,
                 min_names_per_bar: int = 10, log=print) -> Panel:
    """Union of trading days across names, with a membership mask.

    Unlike the crypto panel this does NOT intersect: intersecting would throw away every
    bar before the youngest name listed, which quietly rebuilds the survivorship problem
    from the other end.
    """
    frames, failed = {}, {}
    for s in symbols:
        try:
            frames[s.upper()] = fetch_equity_bars(s, source, years, cache_dir)
        except Exception as e:                              # a dead ticker is data, not a crash
            failed[s.upper()] = f"{type(e).__name__}: {e}"
    if failed:
        log(f"  {len(failed)} symbols unavailable and dropped: " +
            ", ".join(f"{k} ({v.split(':')[0]})" for k, v in list(failed.items())[:6]) +
            ("..." if len(failed) > 6 else ""))
    if len(frames) < min_names_per_bar:
        raise ValueError(f"only {len(frames)} usable symbols; need at least {min_names_per_bar}")

    idx = None
    for df in frames.values():
        i = pd.DatetimeIndex(df["open_time"])
        idx = i if idx is None else idx.union(i)
    idx = idx.sort_values()
    syms = sorted(frames)
    lc = np.full((len(idx), len(syms)), np.nan)
    lo = np.full((len(idx), len(syms)), np.nan)
    for j, s in enumerate(syms):
        d = frames[s].set_index("open_time").reindex(idx)
        lc[:, j] = np.log(d["close"].to_numpy(float))
        lo[:, j] = np.log(d["open"].to_numpy(float))

    mask = build_membership(idx, syms, load_universe(universe_path)) & np.isfinite(lc)
    keep = mask.sum(axis=1) >= min_names_per_bar
    if keep.sum() < 250:
        raise ValueError(f"only {keep.sum()} bars have {min_names_per_bar}+ names")
    idx, lc, lo, mask = idx[keep], lc[keep], lo[keep], mask[keep]
    times = idx.to_numpy(dtype="datetime64[ns]")
    p = Panel(open_time=times, close_time=times, log_close=lc, log_open=lo,
              symbols=syms, bar="1d", mask=mask)
    if universe_path is None:
        log("  WARNING: no point-in-time universe file. Every name in this panel is one "
            "that still exists today, so its history is conditioned on survival. Treat "
            "any positive result as an upper bound until you supply --universe.")
    return p
