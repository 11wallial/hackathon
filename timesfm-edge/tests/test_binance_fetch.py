"""Exercise the Binance loader against a local stand-in server.

This path has never run for real (the build container has no egress), and untested
network code is exactly where a first live run breaks. The stand-in speaks the real
kline wire format: a list of arrays whose first six fields are
[open_time_ms, open, high, low, close, volume], paged by startTime with limit 1000.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

from tfm_edge.data import binance as bn
from tfm_edge.data.panel import panel_from_frames

BAR_MS = 3_600_000
START_MS = 1_600_000_000_000 // BAR_MS * BAR_MS


class _Handler(BaseHTTPRequestHandler):
    n_bars = 2500

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        start = int(q.get("startTime", [START_MS])[0])
        limit = int(q.get("limit", [1000])[0])
        sym = q.get("symbol", ["X"])[0]
        first = max(0, (start - START_MS) // BAR_MS)
        rows = []
        base = 100.0 + (hash(sym) % 50)
        for i in range(first, min(first + limit, self.n_bars)):
            t = START_MS + i * BAR_MS
            c = base + np.sin(i / 50.0) * 5 + i * 0.01
            rows.append([t, f"{c-0.3:.4f}", f"{c+0.6:.4f}", f"{c-0.6:.4f}", f"{c:.4f}", "123.4",
                         t + BAR_MS - 1, "0", 0, "0", "0", "0"])
        body = json.dumps(rows).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/klines"
    srv.shutdown()


@pytest.fixture
def patched(server, monkeypatch, tmp_path):
    monkeypatch.setitem(bn._BASE, "um", server)
    monkeypatch.setattr(bn.time, "sleep", lambda *_: None)
    # the stand-in's bars end well before "now"; ask for a window that covers them all
    monkeypatch.setattr(bn.pd.Timestamp, "utcnow",
                        staticmethod(lambda: pd.Timestamp(START_MS + 2500 * BAR_MS, unit="ms", tz="UTC")))
    return str(tmp_path)


def test_fetch_paginates_validates_and_caches(patched):
    df = bn.fetch_klines("BTCUSDT", "1h", years=1.0, market="um", cache_dir=patched)
    assert len(df) > 2000
    assert list(df.columns[:6]) == ["open_time", "open", "high", "low", "close", "volume"]
    assert df["open_time"].is_monotonic_increasing and not df["open_time"].duplicated().any()
    # gapless: validate_bars would have raised otherwise, but assert it directly
    assert (df["open_time"].diff().dropna() == pd.Timedelta("1h")).all()
    # knowable_at is the close, never the open: this is the no-look-ahead contract
    assert (df["knowable_at"] == df["open_time"] + pd.Timedelta("1h")).all()
    assert (df["high"] >= df["close"]).all() and (df["low"] <= df["close"]).all()

    # second call is served from the parquet cache, not the network
    bn._BASE["um"] = "http://127.0.0.1:1/should-not-be-called"
    again = bn.fetch_klines("BTCUSDT", "1h", years=1.0, market="um", cache_dir=patched)
    assert len(again) == len(df)


def test_panel_alignment_across_symbols(patched):
    frames = {s: bn.fetch_klines(s, "1h", 1.0, market="um", cache_dir=patched)
              for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT")}
    frames["SOLUSDT"] = frames["SOLUSDT"].iloc[300:].reset_index(drop=True)   # ragged history
    p = panel_from_frames(frames, "1h")
    assert p.n_assets == 3
    assert p.log_close.shape[0] == len(frames["SOLUSDT"])     # intersection, not union
    assert np.isfinite(p.log_close).all() and np.isfinite(p.log_open).all()
    assert p.symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_cross_sectional_run_over_fetched_bars(patched, tmp_path):
    """The whole live path: fetch -> validate -> align -> residualise -> walk-forward ->
    book -> deflated Sharpe. Exercised here because the container that built this cannot
    reach Binance, and this is the code that runs first on a machine that can."""
    from tfm_edge.analysis.panel_run import run
    from tfm_edge.config import (CostModel, CrossSectionConfig, DataConfig, ForecastConfig,
                                 RunConfig, StatsConfig, StrategyConfig, WalkForwardConfig)
    syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
    cfg = RunConfig(
        name="live_path",
        data=DataConfig(source="binance", market="um", bar="1h", years=1.0, cache_dir=patched),
        cross_section=CrossSectionConfig(enabled=True, symbols=syms, residualise="beta"),
        forecast=ForecastConfig(forecaster="ar1", context_len=128, horizon=1),
        walkforward=WalkForwardConfig(n_splits=3, embargo_bars=6, min_train_bars=600),
        strategy=StrategyConfig(top_fractions=(0.34,), smoothing_halflives=(0.0, 5.0),
                                rebalance_intervals=(1,)),
        costs=CostModel(), stats=StatsConfig(ledger_path=str(tmp_path / "l.json")),
        report_dir=str(tmp_path),
    )
    res = run(cfg, log=lambda *a: None)
    assert res["n_assets"] == len(syms) and res["n_test_bars"] > 100
    assert np.isfinite(res["candidate"]["cross_sectional_ic"])
    assert res["gate"]["verdict"] in ("STOP", "PROCEED", "PROCEED_FRAGILE", "PROCEED_UNDERPOWERED")
    assert (tmp_path / "xs_live_path.md").exists()
