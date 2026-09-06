"""TimesFM wrapper (2.5 and 3.0 checkpoints), zero-shot, with a versioned cache.

Input modes
  log_price : feed log close levels; the forecast at step H minus the last log
              close is the H-bar log-return forecast. Quantiles shift the same way.
  log_return: feed one-bar log returns; step forecasts are summed to H. Quantile
              spreads are combined under an independence assumption
              (sqrt of summed squared deviations), which is exact for H=1 and an
              approximation otherwise. Both modes count as separate variants.

LICENCE NOTE: TimesFM 3.0 pretrained weights are distributed under
timesfm-non-commercial-license-v1.0 (non-commercial, non-production use only).
Trading real money on them is production use. TimesFM 2.5 weights are Apache-2.0.
The harness defaults to 2.5 for that reason; 3.0 is available for research runs.
"""
from __future__ import annotations

import numpy as np

from .base import ForecastDist
from .cache import ForecastCache


def _family(model_id: str, family: str) -> str:
    if family != "auto":
        return family
    return "timesfm3" if "3.0" in model_id or "timesfm-3" in model_id else "timesfm2.5"


class TimesFMForecaster:
    name = "timesfm"

    def __init__(self, model_id: str, family: str = "auto", input_mode: str = "log_price",
                 context_len: int = 512, device: str = "cpu", batch_size: int = 32,
                 cache_dir: str = "cache/forecasts", max_horizon: int = 1):
        if input_mode not in ("log_price", "log_return"):
            raise ValueError(input_mode)
        self.model_id, self.family = model_id, _family(model_id, family)
        self.input_mode, self.context_len, self.device, self.batch_size = input_mode, context_len, device, batch_size
        self.max_horizon = max_horizon
        self._model = None
        try:
            import importlib.metadata as md
            lib_version = md.version("timesfm")
        except Exception:  # pragma: no cover
            lib_version = "unknown"
        self.version = f"{model_id}@timesfm=={lib_version}"
        self.cache = ForecastCache(cache_dir, self.version, {"family": self.family, "input_mode": input_mode, "context_len": context_len})
        self.n_cache_hits = 0
        self.n_model_calls = 0

    # -- lifecycle ------------------------------------------------------------
    def fit(self, train_returns):
        return None  # zero-shot; the training fold is only used by the baselines

    def _load(self):
        if self._model is not None:
            return
        if self.family == "timesfm3":
            from timesfm3 import ModelConfig, TimesFM3Evaluator
            self._model = TimesFM3Evaluator(ModelConfig(checkpoint_path=self.model_id, per_core_batch_size=self.batch_size, device=self.device))
        else:
            import timesfm
            m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self.model_id)
            m.compile(timesfm.ForecastConfig(
                max_context=self.context_len, max_horizon=max(self.max_horizon, 1),
                normalize_inputs=True, use_continuous_quantile_head=True,
                force_flip_invariance=True, infer_is_positive=False, fix_quantile_crossing=True,
                per_core_batch_size=self.batch_size,
            ))
            self._model = m

    # -- raw model call --------------------------------------------------------
    def _raw(self, inputs: list[np.ndarray], horizon: int) -> tuple[np.ndarray, np.ndarray]:
        """Returns point (B,H) and quantiles (B,H,9)."""
        self._load()
        self.n_model_calls += len(inputs)
        if self.family == "timesfm3":
            outs = list(self._model.predict_batch(
                [x.astype(np.float32) for x in inputs], horizon=horizon, return_quantiles=True,
                use_symmetric_averaging=False, make_positive=False, sort_quantiles=True, univariate=True))
            point = np.stack([o.forecast for o in outs])
            q = np.stack([o.quantiles for o in outs])
        else:
            point, q = self._model.forecast(horizon=horizon, inputs=[x.astype(np.float32) for x in inputs])
            point, q = np.asarray(point)[:, :horizon], np.asarray(q)[:, :horizon, :]
        if q.shape[-1] == 10:      # 2.5 returns [mean, q0.1..q0.9]
            q = q[..., 1:]
        return point.astype(np.float64), q.astype(np.float64)

    # -- public ------------------------------------------------------------------
    def predict(self, windows: list[np.ndarray], horizon: int) -> ForecastDist:
        n = len(windows)
        point = np.empty(n)
        quant = np.empty((n, 9))
        todo, todo_idx, keys = [], [], []
        for i, w in enumerate(windows):
            w = w[-self.context_len:]
            x = w if self.input_mode == "log_price" else np.diff(w)
            k = self.cache.key(x, horizon)
            hit = self.cache.get(k)
            if hit is not None:
                point[i], quant[i] = hit[0], hit[1]
                self.n_cache_hits += 1
            else:
                todo.append(x); todo_idx.append(i); keys.append(k)
        for s in range(0, len(todo), self.batch_size):
            batch = todo[s:s + self.batch_size]
            p_steps, q_steps = self._raw(batch, horizon)
            for j, x in enumerate(batch):
                if self.input_mode == "log_price":
                    last = x[-1]
                    p = p_steps[j, horizon - 1] - last
                    q = q_steps[j, horizon - 1, :] - last
                else:
                    p = p_steps[j, :horizon].sum()
                    med = q_steps[j, :horizon, 4]
                    dev = q_steps[j, :horizon, :] - med[:, None]
                    q = p + np.sign(dev.sum(0)) * np.sqrt((dev ** 2).sum(0))
                q = np.sort(q)
                i = todo_idx[j]
                point[i], quant[i] = p, q
                self.cache.put(keys[j], np.array(p), q)
        return ForecastDist(point, quant)
