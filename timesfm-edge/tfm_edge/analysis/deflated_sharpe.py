"""Probabilistic and Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

Bonferroni on a hit rate is a blunt instrument: it ignores how many observations you
have, how fat the tails are, and how correlated the variants you tried were. The
Deflated Sharpe Ratio is the right correction for a *strategy* result. It asks: given
that I tried N configurations, and given the length, skew and kurtosis of this return
stream, what is the probability its true Sharpe is above zero?

DSR is the gate criterion for any selective strategy in this repo, because the
threshold sweep alone is a multiple-testing surface and hit rate cannot see it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

EULER_MASCHERONI = 0.5772156649015329


def sharpe(returns: np.ndarray) -> float:
    """Per-observation Sharpe. Multiply by sqrt(obs per year) to annualise."""
    sd = returns.std(ddof=1)
    return float(returns.mean() / sd) if sd > 0 else 0.0


def probabilistic_sharpe(returns: np.ndarray, benchmark_sr: float = 0.0) -> float:
    """P(true per-observation Sharpe > benchmark_sr), accounting for skew and kurtosis.

    Negative skew and fat tails both inflate the standard error of an observed Sharpe,
    which is exactly the shape a stop-loss-bracketed strategy produces."""
    n = len(returns)
    if n < 30:
        return float("nan")
    sr = sharpe(returns)
    sd = returns.std(ddof=1)
    if sd == 0:
        return float("nan")
    z = (returns - returns.mean()) / sd
    skew = float(np.mean(z ** 3))
    kurt = float(np.mean(z ** 4))
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    return float(norm.cdf((sr - benchmark_sr) * np.sqrt(n - 1) / np.sqrt(denom)))


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """Expected maximum per-observation Sharpe across n_trials of a ZERO-edge strategy.

    This is the bar a winner must clear to be more than the best of N coin flips. It
    grows like sqrt(2 log N), so twenty variants is not twice as suspicious as ten,
    it is only about 1.1x, but a thousand is 1.8x."""
    if n_trials < 2 or sharpe_variance <= 0:
        return 0.0
    n = float(n_trials)
    a = norm.ppf(1.0 - 1.0 / n)
    b = norm.ppf(1.0 - 1.0 / (n * np.e))
    return float(np.sqrt(sharpe_variance) * ((1.0 - EULER_MASCHERONI) * a + EULER_MASCHERONI * b))


@dataclass
class DSRResult:
    n_obs: int
    sharpe_per_obs: float
    sharpe_annual: float
    skew: float
    kurtosis: float
    n_trials: int
    expected_max_null_sharpe: float
    psr_vs_zero: float
    deflated_sharpe: float      # P(true Sharpe > best-of-N null); this is the gate number
    passes: bool


def deflated_sharpe(returns: np.ndarray, n_trials: int, trial_sharpes: np.ndarray | None = None,
                    obs_per_year: float = 252.0, alpha: float = 0.05) -> DSRResult:
    """Deflate the observed Sharpe by the best-of-N-nulls benchmark and test it.

    trial_sharpes: the per-observation Sharpes of every variant tried. Their variance is
    what sets the null benchmark. If you cannot supply them, the variance of a zero-edge
    Sharpe estimate, 1/(n-1), is used, which is the optimistic assumption because real
    variants disagree more than that."""
    n = len(returns)
    sr = sharpe(returns)
    sd = returns.std(ddof=1)
    z = (returns - returns.mean()) / sd if sd > 0 else returns * 0
    skew, kurt = float(np.mean(z ** 3)), float(np.mean(z ** 4))
    var_sr = float(np.var(trial_sharpes, ddof=1)) if trial_sharpes is not None and len(trial_sharpes) > 1 else 1.0 / max(n - 1, 1)
    sr_star = expected_max_sharpe(n_trials, var_sr)
    dsr = probabilistic_sharpe(returns, sr_star)
    return DSRResult(
        n_obs=n, sharpe_per_obs=sr, sharpe_annual=sr * np.sqrt(obs_per_year),
        skew=skew, kurtosis=kurt, n_trials=n_trials, expected_max_null_sharpe=sr_star,
        psr_vs_zero=probabilistic_sharpe(returns, 0.0), deflated_sharpe=dsr,
        passes=bool(np.isfinite(dsr) and dsr > 1 - alpha),
    )
