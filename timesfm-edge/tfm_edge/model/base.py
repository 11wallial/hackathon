"""Forecaster protocol. Every forecaster, foundation model or baseline, speaks this.

A forecast is a distribution over the H-bar log return measured from close[t].
Quantile levels are fixed at the nine TimesFM levels so Test B is comparable
across models.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

QUANTILE_LEVELS = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])


@dataclass(frozen=True)
class ForecastDist:
    point: np.ndarray       # (N,) predicted H-bar log return (median)
    quantiles: np.ndarray   # (N, 9) at QUANTILE_LEVELS, non-decreasing along axis 1

    def __post_init__(self):
        if self.quantiles.shape != (len(self.point), len(QUANTILE_LEVELS)):
            raise ValueError(f"quantiles shape {self.quantiles.shape} != ({len(self.point)}, 9)")

    def sorted(self) -> "ForecastDist":
        return ForecastDist(self.point, np.sort(self.quantiles, axis=1))


class Forecaster(Protocol):
    name: str

    def fit(self, train_returns: np.ndarray) -> None:
        """Fit on training-fold returns. Zero-shot models do nothing here."""

    def predict(self, log_close_windows: list[np.ndarray], horizon: int) -> ForecastDist:
        """Each window is log close up to and including the decision bar."""


def normal_quantiles(mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    from scipy.stats import norm
    z = norm.ppf(QUANTILE_LEVELS)
    return mu[:, None] + sigma[:, None] * z[None, :]
