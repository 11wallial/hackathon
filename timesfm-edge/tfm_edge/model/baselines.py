"""Statistical baselines. Each is deliberately simple; if TimesFM cannot beat these
it has no business trading.

Directional baselines (Test A): zero, last_sign, ar1
Volatility baselines (Test B): ewma, garch
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy.stats import norm, t as student_t

from .base import QUANTILE_LEVELS, ForecastDist, normal_quantiles


def _window_returns(w: np.ndarray) -> np.ndarray:
    return np.diff(w)


class ZeroForecaster:
    """Predicts zero return. Its 'hit rate' is undefined (never takes a side), so
    Test A compares against the best constant-sign predictor instead (see metrics)."""
    name = "zero"

    def fit(self, train_returns):
        self.sigma = float(np.nanstd(train_returns))

    def predict(self, windows, horizon):
        n = len(windows)
        mu = np.zeros(n)
        return ForecastDist(mu, normal_quantiles(mu, np.full(n, self.sigma * np.sqrt(horizon))))


class LastSignForecaster:
    """Momentum-of-one-bar: predicts the sign of the last return with magnitude
    equal to the training mean absolute return."""
    name = "last_sign"

    def fit(self, train_returns):
        r = train_returns[~np.isnan(train_returns)]
        self.mag = float(np.mean(np.abs(r)))
        self.sigma = float(np.std(r))

    def predict(self, windows, horizon):
        last = np.array([_window_returns(w)[-1] for w in windows])
        mu = np.sign(last) * self.mag * horizon
        return ForecastDist(mu, normal_quantiles(mu, np.full(len(mu), self.sigma * np.sqrt(horizon))))


class AR1Forecaster:
    """r[t+1] = c + phi r[t] + e, fitted by OLS on the training fold, iterated H steps."""
    name = "ar1"

    def fit(self, train_returns):
        r = train_returns[~np.isnan(train_returns)]
        x, y = r[:-1], r[1:]
        X = np.column_stack([np.ones_like(x), x])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        self.c, self.phi = float(beta[0]), float(beta[1])
        resid = y - X @ beta
        self.sigma = float(np.std(resid))

    def predict(self, windows, horizon):
        last = np.array([_window_returns(w)[-1] for w in windows])
        mu = np.zeros(len(last))
        step = last
        for _ in range(horizon):
            step = self.c + self.phi * step
            mu += step
        return ForecastDist(mu, normal_quantiles(mu, np.full(len(mu), self.sigma * np.sqrt(horizon))))


class EWMAVolForecaster:
    """RiskMetrics: sigma^2[t+1] = lam sigma^2[t] + (1-lam) r[t]^2, zero mean, normal quantiles."""
    name = "ewma"

    def __init__(self, lam: float = 0.94):
        self.lam = lam

    def fit(self, train_returns):
        r = train_returns[~np.isnan(train_returns)]
        self.sigma0 = float(np.std(r))

    def predict(self, windows, horizon):
        sig = np.empty(len(windows))
        for i, w in enumerate(windows):
            r = _window_returns(w)
            s2 = self.sigma0 ** 2
            for x in r:
                s2 = self.lam * s2 + (1 - self.lam) * x * x
            sig[i] = np.sqrt(s2 * horizon)
        mu = np.zeros(len(windows))
        return ForecastDist(mu, normal_quantiles(mu, sig))


class GARCHForecaster:
    """GARCH(1,1) with Student-t innovations, fitted once per training fold with the
    `arch` package, then filtered through each test context with the fitted
    parameters (no refit on test data, so no leak)."""
    name = "garch"

    def fit(self, train_returns):
        from arch import arch_model
        r = train_returns[~np.isnan(train_returns)] * 100.0  # arch likes percent units
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = arch_model(r, mean="Zero", vol="GARCH", p=1, q=1, dist="t").fit(disp="off")
        p = res.params
        self.omega, self.alpha, self.beta, self.nu = float(p["omega"]), float(p["alpha[1]"]), float(p["beta[1]"]), float(p["nu"])
        self.uncond = self.omega / max(1e-12, 1 - self.alpha - self.beta) if self.alpha + self.beta < 1 else float(np.var(r))
        self.converged = bool(res.convergence_flag == 0)

    def predict(self, windows, horizon):
        sig = np.empty(len(windows))
        for i, w in enumerate(windows):
            r = _window_returns(w) * 100.0
            s2 = self.uncond
            for x in r:
                s2 = self.omega + self.alpha * x * x + self.beta * s2
            # multi-step variance forecast, summed over the horizon
            total, s2h = 0.0, s2
            for _ in range(horizon):
                total += s2h
                s2h = self.omega + (self.alpha + self.beta) * s2h
            sig[i] = np.sqrt(total) / 100.0
        mu = np.zeros(len(windows))
        # scale t so that variance = sig^2
        scale = sig * np.sqrt((self.nu - 2) / self.nu)
        q = mu[:, None] + scale[:, None] * student_t.ppf(QUANTILE_LEVELS, self.nu)[None, :]
        return ForecastDist(mu, q)


BASELINES = {
    "zero": ZeroForecaster, "last_sign": LastSignForecaster, "ar1": AR1Forecaster,
    "ewma": EWMAVolForecaster, "garch": GARCHForecaster,
}
