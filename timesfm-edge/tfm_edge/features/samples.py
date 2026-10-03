"""Point-in-time samples.

For a decision made at index t (i.e. at close_time[t], the first moment bar t is
knowable), we define:

    context      : the model input, everything up to and including close[t]
    y_cc         : forecast TARGET, log(close[t+H]) - log(close[t])
    y_oo         : TRADABLE realised return, log(open[t+1+H]) - log(open[t+1])
                   i.e. enter at the open of the bar after the decision, exit at
                   the open H bars later. This is what a trade would actually earn.
    decision_at  : close_time[t]
    executes_at  : open_time[t+1]  (== close_time[t] on a gapless feed)

Hard constraint 2 lives here: nothing in `context` has index > t, and both
targets start strictly after the decision. The test suite checks this by
shifting the series and asserting the leak is caught.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Samples:
    t: np.ndarray                 # decision bar index
    decision_at: np.ndarray       # datetime64, when the decision is knowable
    executes_at: np.ndarray       # datetime64, first fill opportunity
    y_cc: np.ndarray              # close-to-close H-bar log return (forecast target)
    y_oo: np.ndarray              # open-to-open H-bar log return (tradable)
    last_ret: np.ndarray          # log(close[t]) - log(close[t-1]) for the last-sign baseline
    horizon: int

    def __len__(self) -> int:
        return len(self.t)

    def subset(self, mask_or_idx) -> "Samples":
        return Samples(self.t[mask_or_idx], self.decision_at[mask_or_idx], self.executes_at[mask_or_idx],
                       self.y_cc[mask_or_idx], self.y_oo[mask_or_idx], self.last_ret[mask_or_idx], self.horizon)


def log_returns(log_close: np.ndarray) -> np.ndarray:
    """r[t] = log_close[t] - log_close[t-1]; r[0] is NaN (unknown)."""
    r = np.full_like(log_close, np.nan)
    r[1:] = np.diff(log_close)
    return r


def build_samples(df: pd.DataFrame, horizon: int, context_len: int) -> Samples:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    lc = np.log(df["close"].to_numpy(np.float64))
    lo = np.log(df["open"].to_numpy(np.float64))
    n = len(df)
    first = max(context_len - 1, 1)           # need a full context and a defined last return
    last = n - 1 - horizon - 1                # need open[t+1+H] to exist
    if last < first:
        raise ValueError("not enough bars for this context_len/horizon")
    t = np.arange(first, last + 1)
    y_cc = lc[t + horizon] - lc[t]
    y_oo = lo[t + 1 + horizon] - lo[t + 1]
    last_ret = lc[t] - lc[t - 1]
    return Samples(
        t=t,
        decision_at=df["close_time"].to_numpy()[t],
        executes_at=df["open_time"].to_numpy()[t + 1],
        y_cc=y_cc, y_oo=y_oo, last_ret=last_ret, horizon=horizon,
    )


def context_window(series: np.ndarray, t: int, context_len: int) -> np.ndarray:
    """series[t-context_len+1 : t+1]. Index t is the LAST element: nothing after it."""
    start = max(0, t - context_len + 1)
    return series[start:t + 1]
