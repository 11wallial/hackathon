from __future__ import annotations

from ..config import ForecastConfig
from .baselines import BASELINES
from .timesfm_wrapper import TimesFMForecaster


def make_forecaster(cfg: ForecastConfig):
    if cfg.forecaster == "timesfm":
        return TimesFMForecaster(cfg.model_id, cfg.model_family, cfg.input_mode, cfg.context_len,
                                 cfg.device, cfg.batch_size, cfg.cache_dir, max_horizon=cfg.horizon)
    if cfg.forecaster in BASELINES:
        return BASELINES[cfg.forecaster]()
    raise ValueError(f"unknown forecaster {cfg.forecaster}")
