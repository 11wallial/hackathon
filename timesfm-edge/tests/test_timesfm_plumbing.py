"""Runs the wrapper against a real TimesFM 3 model object with random weights.
Proves shapes, caching, determinism and the return conversion, without needing
the pretrained checkpoint (which needs network access and a licence check)."""
import os

import numpy as np
import pytest

timesfm3 = pytest.importorskip("timesfm3")


@pytest.fixture(scope="module")
def tiny_model(tmp_path_factory):
    from safetensors.torch import save_file
    from timesfm3 import ModelConfig, TimesFM3Evaluator, configs
    from timesfm3.timesfm3_forecaster import _make_torch_model
    d = tmp_path_factory.mktemp("tfm")
    p = str(d / "tiny.safetensors")
    rb = configs.ResidualBlockConfig(hidden_dims=32, output_dims=32, use_bias=False, activation="relu")
    tc = configs.StackedTransformersConfig(num_layers=1, transformer=configs.TransformerConfig(
        model_dims=32, hidden_dims=32, num_heads=2, attention_norm="rms", feedforward_norm="rms", qk_norm="rms",
        use_rope_seq=True, use_rope_var=True, use_bias=False, ff_activation="relu", deterministic=True))
    cfg = ModelConfig(checkpoint_path=p, residual_block_config=rb, transformer_config=tc, device="cpu", per_core_batch_size=4)
    m = _make_torch_model(cfg)
    save_file({k: v.contiguous() for k, v in m.state_dict().items()}, p)
    return p, TimesFM3Evaluator(cfg), str(d / "cache")


def test_wrapper_shapes_cache_and_determinism(tiny_model):
    from tfm_edge.model.timesfm_wrapper import TimesFMForecaster
    p, model, cache = tiny_model
    f = TimesFMForecaster(p, family="timesfm3", input_mode="log_price", context_len=64, cache_dir=cache)
    f._model = model
    rng = np.random.default_rng(0)
    wins = [np.log(100 + np.cumsum(rng.standard_normal(90))) for _ in range(6)]
    a = f.predict(wins, 1)
    assert a.point.shape == (6,) and a.quantiles.shape == (6, 9)
    assert np.all(np.diff(a.quantiles, axis=1) >= 0)
    assert f.n_model_calls == 6
    b = f.predict(wins, 1)
    assert f.n_cache_hits == 6 and np.array_equal(a.point, b.point)
    # a fresh instance pointed at the same cache reproduces without calling the model
    g = TimesFMForecaster(p, family="timesfm3", input_mode="log_price", context_len=64, cache_dir=cache)
    c = g.predict(wins, 1)
    assert g.n_model_calls == 0 and np.array_equal(a.quantiles, c.quantiles)


def test_return_mode_multi_horizon(tiny_model):
    from tfm_edge.model.timesfm_wrapper import TimesFMForecaster
    p, model, cache = tiny_model
    f = TimesFMForecaster(p, family="timesfm3", input_mode="log_return", context_len=64, cache_dir=cache)
    f._model = model
    rng = np.random.default_rng(1)
    wins = [np.log(100 + np.cumsum(rng.standard_normal(90))) for _ in range(3)]
    o = f.predict(wins, 4)
    assert o.point.shape == (3,) and np.all(np.diff(o.quantiles, axis=1) >= 0)
