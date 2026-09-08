"""Test A and Test B metrics. All confidence intervals use a circular block
bootstrap because overlapping H-bar labels and volatility clustering make the
per-sample hit indicators serially dependent; an i.i.d. bootstrap would be
optimistic."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.stats import norm, spearmanr

from ..model.base import QUANTILE_LEVELS

INTERVALS = [(0, 8, 0.8), (1, 7, 0.6), (2, 6, 0.4), (3, 5, 0.2)]  # (lo idx, hi idx, nominal)


def block_bootstrap_means(x: np.ndarray, n_boot: int, block_len: int, seed: int) -> np.ndarray:
    """Circular block bootstrap of the mean of x. Returns (n_boot,) resampled means."""
    rng = np.random.default_rng(seed)
    n = len(x)
    if n == 0:
        return np.full(n_boot, np.nan)
    L = max(1, min(block_len, n))
    n_blocks = int(np.ceil(n / L))
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offs = np.arange(L)
    idx = (starts[:, :, None] + offs[None, None, :]).reshape(n_boot, -1)[:, :n] % n
    return x[idx].mean(axis=1)


def default_block_len(n: int, horizon: int) -> int:
    return int(max(horizon, np.ceil(n ** (1 / 3))))


@dataclass
class HitRateResult:
    n: int
    hit_rate: float
    ci_lo: float            # two-sided (1-alpha) bootstrap percentile CI
    ci_hi: float
    ci_lo_adj: float        # lower bound at Bonferroni-adjusted alpha (one-sided), used by the gate
    p_value: float          # one-sided H0: hit rate <= 0.5, from bootstrap SE
    block_len: int
    n_tests_adjusted_for: int


def hit_rate(pred: np.ndarray, y: np.ndarray, horizon: int, n_boot: int, seed: int,
             alpha: float, n_tests: int) -> HitRateResult:
    mask = (pred != 0) & (y != 0)
    hits = (np.sign(pred[mask]) == np.sign(y[mask])).astype(float)
    n = int(mask.sum())
    if n < 30:
        return HitRateResult(n, np.nan, np.nan, np.nan, np.nan, np.nan, 0, n_tests)
    L = default_block_len(n, horizon)
    boots = block_bootstrap_means(hits, n_boot, L, seed)
    hr = float(hits.mean())
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    alpha_adj = alpha / max(1, n_tests)
    lo_adj = float(np.percentile(boots, 100 * alpha_adj))
    se = float(boots.std(ddof=1))
    p = float(1 - norm.cdf((hr - 0.5) / se)) if se > 0 else (0.0 if hr > 0.5 else 1.0)
    return HitRateResult(n, hr, float(lo), float(hi), lo_adj, p, L, n_tests)


@dataclass
class ICResult:
    n: int
    ic: float
    p_value: float
    ci_lo: float
    ci_hi: float


def information_coefficient(pred: np.ndarray, y: np.ndarray, horizon: int, n_boot: int, seed: int, alpha: float) -> ICResult:
    n = len(y)
    if n < 30 or np.std(pred) == 0:
        return ICResult(n, np.nan, np.nan, np.nan, np.nan)
    rho, p = spearmanr(pred, y)
    rng = np.random.default_rng(seed)
    L = default_block_len(n, horizon)
    n_blocks = int(np.ceil(n / L))
    vals = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx = (starts[:, None] + np.arange(L)[None, :]).reshape(-1)[:n] % n
        vals[b] = spearmanr(pred[idx], y[idx])[0]
    lo, hi = np.nanpercentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return ICResult(n, float(rho), float(p), float(lo), float(hi))


def best_constant_sign_rate(y: np.ndarray) -> float:
    """What 'always long' or 'always short' would score. The zero forecaster's
    honest comparator: any directional model must beat the majority class."""
    nz = y[y != 0]
    return float(max(np.mean(nz > 0), np.mean(nz < 0)))


def break_even_hit_rate(y_tradable: np.ndarray, round_trip_cost_frac: float) -> float:
    """If every bar is traded on sign(forecast) and |realised move| is independent
    of being right, E[net] = (2p - 1) E|r| - c. Setting E[net]=0: p* = 1/2 + c / (2 E|r|).
    The independence assumption is optimistic for the trader (errors tend to be
    big moves), so the true break-even is higher than this number."""
    m = float(np.mean(np.abs(y_tradable)))
    return 0.5 + round_trip_cost_frac / (2 * m)


@dataclass
class PnLResult:
    cost_multiplier: float
    trade_fraction: float
    mean_net_per_bar: float
    sharpe_annualised: float
    total_net_log_return: float


def sign_trading_pnl(pred: np.ndarray, y_tradable: np.ndarray, round_trip_cost_frac: float,
                     cost_multiplier: float, bars_per_year: float, horizon: int) -> PnLResult:
    """Naive: trade sign(pred) on every non-zero forecast, hold H bars, pay a full
    round trip each time. Non-overlapping execution is assumed (H=1 exact).
    This is a diagnostic, not the Phase 2 decision rule."""
    side = np.sign(pred)
    gross = side * y_tradable
    cost = np.abs(side) * round_trip_cost_frac * cost_multiplier
    net = gross - cost
    mu, sd = net.mean(), net.std(ddof=1)
    per_year = bars_per_year / horizon
    sharpe = float(mu / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    return PnLResult(cost_multiplier, float(np.mean(side != 0)), float(mu), sharpe, float(net.sum()))


# ---------------------------------------------------------------- Test B ----
@dataclass
class CalibrationResult:
    n: int
    interval_coverage: dict         # nominal -> empirical
    quantile_coverage: dict         # level -> P(y <= q_level)
    mean_abs_coverage_error: float  # over the four central intervals
    pinball_loss: float             # mean over 9 levels
    pinball_by_level: dict
    crps_proxy: float               # 2 * mean pinball, a discrete CRPS approximation


def pinball(y: np.ndarray, q: np.ndarray, level: float) -> np.ndarray:
    d = y - q
    return np.maximum(level * d, (level - 1) * d)


def calibration(y: np.ndarray, quantiles: np.ndarray) -> CalibrationResult:
    n = len(y)
    q = np.sort(quantiles, axis=1)
    icov = {}
    for lo, hi, nominal in INTERVALS:
        icov[nominal] = float(np.mean((y >= q[:, lo]) & (y <= q[:, hi])))
    qcov = {float(l): float(np.mean(y <= q[:, k])) for k, l in enumerate(QUANTILE_LEVELS)}
    mace = float(np.mean([abs(icov[nm] - nm) for _, _, nm in INTERVALS]))
    pb = {float(l): float(pinball(y, q[:, k], l).mean()) for k, l in enumerate(QUANTILE_LEVELS)}
    mean_pb = float(np.mean(list(pb.values())))
    return CalibrationResult(n, icov, qcov, mace, mean_pb, pb, 2 * mean_pb)


def to_dict(obj) -> dict:
    return asdict(obj)
