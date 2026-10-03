from __future__ import annotations

import pandas as pd

from ..config import DataConfig
from . import synthetic
from .csv_loader import load_csv


def load_bars(cfg: DataConfig) -> pd.DataFrame:
    if cfg.source == "binance":
        from .binance import fetch_klines
        return fetch_klines(cfg.symbol, cfg.bar, cfg.years, market=cfg.market, cache_dir=cfg.cache_dir)
    if cfg.source == "csv":
        if not cfg.csv_path:
            raise ValueError("data.csv_path required for source=csv")
        return load_csv(cfg.csv_path, cfg.bar)
    if cfg.source == "synthetic":
        return synthetic.generate(cfg.synthetic_kind, cfg.synthetic_n, bar=cfg.bar,
                                  seed=cfg.synthetic_seed, phi=cfg.synthetic_phi)
    raise ValueError(f"unknown data source {cfg.source}")
