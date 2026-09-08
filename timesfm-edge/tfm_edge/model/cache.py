"""Content-addressed forecast cache. A given (model version, config, input window)
always yields the same stored forecast, which makes runs reproducible and lets a
TimesFM sweep resume after interruption."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


class ForecastCache:
    def __init__(self, cache_dir: str, model_version: str, cfg: dict):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.prefix = hashlib.sha256(json.dumps({"v": model_version, **cfg}, sort_keys=True).encode()).hexdigest()[:16]

    def key(self, window: np.ndarray, horizon: int) -> str:
        h = hashlib.sha256(np.ascontiguousarray(window, dtype=np.float32).tobytes())
        h.update(f"|H={horizon}".encode())
        return f"{self.prefix}_{h.hexdigest()[:24]}"

    def get(self, key: str):
        p = self.dir / f"{key}.npz"
        if p.exists():
            z = np.load(p)
            return z["point"], z["quantiles"]
        return None

    def put(self, key: str, point: np.ndarray, quantiles: np.ndarray) -> None:
        np.savez(self.dir / f"{key}.npz", point=point, quantiles=quantiles)
