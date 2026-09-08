"""Equity loader and point-in-time universe.

The two failure modes that ruin an equity backtest are unadjusted corporate actions and
survivorship, so both are tested directly rather than assumed away.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

from tfm_edge.data import equity as eq

N_DAYS = 1400


def _series(sym: str, split_at: int | None = None):
    rng = np.random.default_rng(abs(hash(sym)) % 2**31)
    r = rng.standard_normal(N_DAYS) * 0.015
    px = 50.0 * np.exp(np.cumsum(r))
    if split_at is not None:
        px[split_at:] /= 2.0            # a raw, unadjusted 2-for-1 split
    days = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=N_DAYS)
    return days, px


KNOWN = {"AAPL", "MSFT", "JNJ", "XOM", "KO", "PG", "WMT", "CVX", "PFE", "INTC", "CSCO", "MRK"}


class _Handler(BaseHTTPRequestHandler):
    split_symbols: set = set()

    def _reject(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path.startswith("/q/d/l"):
            sym = q["s"][0].split(".")[0].upper()
            if sym not in KNOWN:
                return self._reject()
            days, px = _series(sym, N_DAYS // 2 if sym in self.split_symbols else None)
            lines = ["Date,Open,High,Low,Close,Volume"]
            for d, p in zip(days, px):
                lines.append(f"{d.date()},{p*0.999:.4f},{p*1.01:.4f},{p*0.99:.4f},{p:.4f},1000")
            body = "\n".join(lines).encode()
            ctype = "text/csv"
        else:
            sym = u.path.rstrip("/").split("/")[-1].upper()
            if sym not in KNOWN:
                return self._reject()
            days, px = _series(sym)
            body = json.dumps({"chart": {"result": [{
                "timestamp": [int(d.timestamp()) for d in days],
                "indicators": {"quote": [{"open": list(px * 0.999), "high": list(px * 1.01),
                                          "low": list(px * 0.99), "close": list(px),
                                          "volume": [1000] * len(px)}],
                               "adjclose": [{"adjclose": list(px)}]}}]}}).encode()
            ctype = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def patched(server, monkeypatch, tmp_path):
    monkeypatch.setattr(eq, "STOOQ_URL", f"{server}/q/d/l/")
    monkeypatch.setattr(eq, "YAHOO_URL", f"{server}/chart/")
    _Handler.split_symbols = set()
    return str(tmp_path)


SYMS = ["AAPL", "MSFT", "JNJ", "XOM", "KO", "PG", "WMT", "CVX", "PFE", "INTC", "CSCO", "MRK"]


def test_stooq_and_yahoo_both_load(patched):
    a = eq.fetch_equity_bars("AAPL", "stooq", years=6.0, cache_dir=patched)
    b = eq.fetch_equity_bars("AAPL", "yahoo", years=6.0, cache_dir=patched)
    for df in (a, b):
        assert len(df) > 900
        assert df["open_time"].is_monotonic_increasing
        assert (df[["open", "high", "low", "close"]] > 0).all().all()


def test_unadjusted_split_is_refused(patched):
    _Handler.split_symbols = {"AAPL"}
    with pytest.raises(eq.UnadjustedPriceError, match="split"):
        eq.fetch_equity_bars("AAPL", "stooq", years=6.0, cache_dir=patched)


def test_dead_ticker_is_dropped_not_fatal(patched):
    p = eq.equity_panel(SYMS + ["DELISTED_NOPE"], source="stooq", years=6.0,
                        cache_dir=patched, min_names_per_bar=5, log=lambda *a: None)
    assert p.n_assets == len(SYMS)


def test_static_universe_is_flagged_as_survivorship(patched):
    p = eq.equity_panel(SYMS, "stooq", 6.0, patched, min_names_per_bar=5, log=lambda *a: None)
    rep = p.survivorship_report()
    assert rep["static_universe"] is True
    assert rep["members_first_bar"] == rep["members_last_bar"] == len(SYMS)


def test_point_in_time_universe_limits_membership(patched, tmp_path):
    """A name is only held while it was a member, and returns across an entry boundary
    are NaN so a re-entry never books the gap as a one-bar profit."""
    upath = tmp_path / "universe.csv"
    rows = [{"symbol": s, "start_date": "2019-01-02", "end_date": ""} for s in SYMS]
    late = (pd.Timestamp.now().normalize() - pd.Timedelta(days=400)).date()
    early = (pd.Timestamp.now().normalize() - pd.Timedelta(days=300)).date()
    rows[0] = {"symbol": "AAPL", "start_date": str(late), "end_date": ""}          # joined late
    rows[1] = {"symbol": "MSFT", "start_date": "2019-01-02", "end_date": str(early)}  # left early
    pd.DataFrame(rows).to_csv(upath, index=False)
    p = eq.equity_panel(SYMS, "stooq", 6.0, patched, universe_path=str(upath),
                        min_names_per_bar=5, log=lambda *a: None)
    m = p.membership()
    ai, mi = p.symbols.index("AAPL"), p.symbols.index("MSFT")
    assert not m[0, ai] and m[-1, ai]
    assert m[0, mi] and not m[-1, mi]
    rep = p.survivorship_report()
    assert rep["static_universe"] is False
    assert rep["members_first_bar"] < len(SYMS)
    # no return is booked across the bar a name enters on
    r = p.returns()
    entry = int(np.argmax(m[:, ai]))
    assert not np.isfinite(r[entry, ai])
    assert np.isfinite(r[entry + 1, ai])


def test_equity_run_end_to_end_with_universe(patched, tmp_path):
    from tfm_edge.analysis.panel_run import run
    from tfm_edge.config import (CostModel, CrossSectionConfig, DataConfig, ForecastConfig,
                                 RunConfig, StatsConfig, StrategyConfig, WalkForwardConfig)
    upath = tmp_path / "u.csv"
    rows = [{"symbol": s, "start_date": "2019-01-02", "end_date": ""} for s in SYMS]
    rows[0]["start_date"] = str((pd.Timestamp.now().normalize() - pd.Timedelta(days=400)).date())
    pd.DataFrame(rows).to_csv(upath, index=False)
    cfg = RunConfig(
        name="eq",
        data=DataConfig(source="equity", equity_source="stooq", bar="1d", years=6.0, cache_dir=patched),
        cross_section=CrossSectionConfig(enabled=True, symbols=SYMS, residualise="beta",
                                         universe_path=str(upath), min_names_per_bar=5),
        forecast=ForecastConfig(forecaster="ar1", context_len=128, horizon=1),
        walkforward=WalkForwardConfig(n_splits=3, embargo_bars=5, min_train_bars=400),
        strategy=StrategyConfig(top_fractions=(0.25,), smoothing_halflives=(0.0, 5.0),
                                rebalance_intervals=(1,)),
        costs=CostModel(0.2, 0.8, 0.5), stats=StatsConfig(ledger_path=str(tmp_path / "l.json")),
        report_dir=str(tmp_path),
    )
    res = run(cfg, log=lambda *a: None)
    assert res["survivorship"]["static_universe"] is False
    # annualisation is derived from the decision timestamps, so a business-day calendar
    # lands near 252-261 rather than on a configured constant
    assert 240 < res["decisions_per_year"] < 270
    assert np.isfinite(res["candidate"]["cross_sectional_ic"])
    md = (tmp_path / "xs_eq.md").read_text()
    assert "point-in-time" in md
