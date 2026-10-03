"""Turnover-aware, selective, sized backtest.

The naive diagnostic in metrics.py (flip on every bar's sign, pay a full round trip) is
the WORST possible execution of a signal and it is what makes marginal setups look
impossible. Two corrections, both of which a real implementation gets for free:

1. TURNOVER. Cost is charged on |w_t - w_{t-1}|, not on holding a position. If the
   signal says long two bars running you hold and pay nothing. A signal with position
   autocorrelation 0.8 pays roughly a third of what flip-every-bar pays.
2. SELECTION. Take a position only when the standardised forecast clears a threshold.
   This concentrates the edge: E[|z| | |z|>tau] rises without bound while the cost per
   trade stays fixed.

Both are swept, and the sweep itself is a multiple-testing surface, so the result is
scored with the Deflated Sharpe Ratio over the whole grid rather than by picking the
best cell and reporting it as if it were the only thing tried.

Sizing is capped at quarter-Kelly. Full Kelly maximises log growth only when the edge
is known exactly; with an estimated edge the variance of the estimate makes full Kelly
overbet, and the drawdown it accepts (routinely >50%) is not survivable by a human who
has to keep deciding to stay in the trade. Quarter-Kelly gives about 7/8 of the growth
at a quarter of the variance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .deflated_sharpe import deflated_sharpe, sharpe

MAX_KELLY_FRACTION = 0.25


def standardise(pred: np.ndarray, ref_scale: np.ndarray | None = None) -> np.ndarray:
    """Convert raw forecasts to z-scores using a point-in-time scale.

    ref_scale must itself be knowable at decision time. Passing None uses the whole
    sample's scale, which is a mild in-sample leak in the SCALE only (not the sign) and
    is acceptable for a diagnostic but not for a live decision rule."""
    s = np.std(pred) if ref_scale is None else ref_scale
    s = np.where(np.asarray(s) > 0, s, 1.0)
    return pred / s


def positions(z: np.ndarray, tau: float, sizing: str = "binary", cap: float = 1.0) -> np.ndarray:
    """Target position in [-cap, cap]. Zero inside the threshold band."""
    if sizing == "binary":
        w = np.sign(z) * cap
    elif sizing == "linear":
        w = np.clip(z / 3.0, -1.0, 1.0) * cap   # 3 sigma forecast = full size
    elif sizing == "kelly":
        # quarter-Kelly on a unit-variance return: f* = mu/sigma^2, here proportional to z
        w = np.clip(z * MAX_KELLY_FRACTION, -1.0, 1.0) * cap
    else:
        raise ValueError(sizing)
    return np.where(np.abs(z) > tau, w, 0.0)


@dataclass
class BacktestResult:
    tau: float
    sizing: str
    trade_fraction: float
    turnover_per_bar: float
    mean_gross_bps: float
    mean_cost_bps: float
    mean_net_bps: float
    sharpe_annual: float
    hit_rate_when_positioned: float
    max_drawdown: float
    n_bars: int


def backtest(z: np.ndarray, y: np.ndarray, cost_rt_frac: float, tau: float,
             bars_per_year: float, sizing: str = "binary",
             prev_w0: float = 0.0) -> tuple[BacktestResult, np.ndarray]:
    """One pass over the sample. Returns the summary and the per-bar net return series.

    y is the TRADABLE return over the holding period (open-to-open in this harness).
    Cost is charged on position change at half the round trip per unit, so a full
    reversal costs exactly one round trip."""
    w = positions(z, tau, sizing)
    prev = np.concatenate([[prev_w0], w[:-1]])
    turnover = np.abs(w - prev)
    cost = turnover * (cost_rt_frac / 2.0)
    gross = w * y
    net = gross - cost
    active = w != 0
    eq = np.cumsum(net)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else 0.0
    hr = float(np.mean(np.sign(w[active]) == np.sign(y[active]))) if active.any() else float("nan")
    return BacktestResult(
        tau=tau, sizing=sizing, trade_fraction=float(active.mean()),
        turnover_per_bar=float(turnover.mean()),
        mean_gross_bps=float(1e4 * gross.mean()), mean_cost_bps=float(1e4 * cost.mean()),
        mean_net_bps=float(1e4 * net.mean()),
        sharpe_annual=float(sharpe(net) * np.sqrt(bars_per_year)),
        hit_rate_when_positioned=hr, max_drawdown=dd, n_bars=len(y),
    ), net


DEFAULT_TAUS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5)
DEFAULT_SIZINGS = ("binary", "linear", "kelly")


@dataclass
class SweepResult:
    grid: list[dict]
    best: dict
    best_net: np.ndarray        # per-bar net returns of the winning cell
    n_cells: int
    dsr: dict
    dsr_passes: bool
    note: str


def sweep(z: np.ndarray, y: np.ndarray, cost_rt_frac: float, bars_per_year: float,
          taus=DEFAULT_TAUS, sizings=DEFAULT_SIZINGS, n_prior_trials: int = 0,
          alpha: float = 0.05) -> SweepResult:
    """Sweep threshold and sizing, then score the WINNER against the whole sweep.

    The deflated Sharpe uses n_cells + n_prior_trials as the trial count, so choosing
    the best cell cannot smuggle in free significance. A cell that looks good only
    because 27 were tried will not pass."""
    rows, series, sharpes = [], [], []
    for s in sizings:
        for t in taus:
            r, net = backtest(z, y, cost_rt_frac, t, bars_per_year, s)
            r2, _ = backtest(z, y, 2 * cost_rt_frac, t, bars_per_year, s)
            d = asdict(r)
            d["sharpe_annual_2x"] = r2.sharpe_annual
            rows.append(d)
            series.append(net)
            sharpes.append(sharpe(net))
    # Chosen on the 2x-cost Sharpe: ranking on the headline picks the most cost-fragile
    # cell. Cells that never trade are excluded, since a Sharpe of exactly zero from
    # standing aside is not a strategy result.
    scores = [r["sharpe_annual_2x"] if r["trade_fraction"] > 0.01 else -np.inf for r in rows]
    best_i = int(np.argmax(scores))
    n_trials = len(rows) + n_prior_trials
    d = deflated_sharpe(series[best_i], n_trials, np.array(sharpes), bars_per_year, alpha)
    return SweepResult(
        grid=rows, best=rows[best_i], best_net=series[best_i], n_cells=len(rows),
        dsr=asdict(d), dsr_passes=d.passes,
        note=(f"best of {len(rows)} cells; deflated against {n_trials} trials "
              f"(null best-of-N Sharpe {d.expected_max_null_sharpe:.4f} per bar)"),
    )


def expanding_standardise(pred: np.ndarray, min_obs: int = 100) -> np.ndarray:
    """Z-score each forecast against the distribution of forecasts BEFORE it.

    Standardising against the whole sample would let the scale of late forecasts inform
    early decisions. An expanding window uses only the past, so a threshold expressed in
    z units is implementable live. Bars before min_obs are left at zero, which means no
    position rather than a position sized off three observations."""
    p = np.asarray(pred, dtype=float)
    n = len(p)
    c1 = np.concatenate([[0.0], np.cumsum(p)])
    c2 = np.concatenate([[0.0], np.cumsum(p ** 2)])
    k = np.arange(n)
    mean = np.divide(c1[:-1], k, out=np.zeros(n), where=k > 0)
    var = np.divide(c2[:-1], k, out=np.zeros(n), where=k > 0) - mean ** 2
    sd = np.sqrt(np.maximum(var, 0.0))
    z = np.divide(p - mean, sd, out=np.zeros(n), where=sd > 0)
    z[:min_obs] = 0.0
    return z
