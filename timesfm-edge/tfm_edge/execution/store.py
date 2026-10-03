"""The ledger: one SQLite file holding every forecast, decision, order, fill and outcome
with timestamps (a hard requirement of the spec), plus the small amount of state the bot
needs between runs.

Design rules:
  - Append-mostly. Nothing that records what the bot saw or did is ever updated in place,
    except an order's status as it moves from accepted to filled.
  - Everything is JSON-serialisable so the UI and the divergence report can read it back.
  - Thread-safe: the UI server and the scheduler both use it.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta      (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS events    (id INTEGER PRIMARY KEY, ts TEXT, level TEXT, kind TEXT, message TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS forecasts (id INTEGER PRIMARY KEY, ts TEXT, asof TEXT, symbol TEXT, model TEXT,
                                      point REAL, quantiles TEXT);
CREATE TABLE IF NOT EXISTS scores    (asof TEXT, symbol TEXT, raw REAL, smoothed REAL, forecast_bps REAL,
                                      PRIMARY KEY (asof, symbol));
CREATE TABLE IF NOT EXISTS plans     (id INTEGER PRIMARY KEY, created_ts TEXT, asof TEXT, for_date TEXT,
                                      status TEXT, mode TEXT, payload TEXT, approved_ts TEXT, approved_by TEXT,
                                      executed_ts TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS orders    (id INTEGER PRIMARY KEY, ts TEXT, plan_id INTEGER, client_id TEXT UNIQUE,
                                      broker_id TEXT, symbol TEXT, side TEXT, qty REAL, kind TEXT, tif TEXT,
                                      status TEXT, filled_qty REAL, filled_avg REAL, raw TEXT);
CREATE TABLE IF NOT EXISTS fills     (id INTEGER PRIMARY KEY, ts TEXT, client_id TEXT, symbol TEXT, side TEXT,
                                      qty REAL, price REAL, commission REAL, UNIQUE (client_id));
CREATE TABLE IF NOT EXISTS equity    (id INTEGER PRIMARY KEY, ts TEXT, session TEXT, equity REAL, cash REAL,
                                      gross REAL, net REAL, source TEXT);
CREATE TABLE IF NOT EXISTS brackets  (symbol TEXT PRIMARY KEY, side TEXT, qty REAL, entry REAL, stop REAL,
                                      target REAL, set_ts TEXT, order_id TEXT);
CREATE TABLE IF NOT EXISTS ideal     (for_date TEXT PRIMARY KEY, asof TEXT, weights TEXT, created_ts TEXT);
CREATE TABLE IF NOT EXISTS rebalances(asof TEXT PRIMARY KEY, ts TEXT);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path, clock=None):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._clock = clock or utcnow

    def now(self) -> str:
        return self._clock()

    @contextmanager
    def tx(self):
        with self._lock:
            self._db.execute("BEGIN")
            try:
                yield self._db
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def q(self, sql: str, args: Iterable = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, tuple(args)).fetchall()]

    def one(self, sql: str, args: Iterable = ()) -> dict | None:
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql: str, args: Iterable = ()) -> int:
        with self._lock:
            return self._db.execute(sql, tuple(args)).lastrowid

    # ---- meta ------------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        r = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(r["value"]) if r else default

    def set(self, key: str, value: Any) -> None:
        self.x("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, json.dumps(value)))

    # ---- events ----------------------------------------------------------------------
    def event(self, level: str, kind: str, message: str, data: Any = None) -> None:
        self.x("INSERT INTO events(ts,level,kind,message,data) VALUES(?,?,?,?,?)",
               (self.now(), level, kind, message, json.dumps(data, default=str) if data is not None else None))

    def events(self, limit: int = 100, min_level: str | None = None) -> list[dict]:
        rows = self.q("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["data"] = json.loads(r["data"]) if r["data"] else None
        return rows

    # ---- plans -----------------------------------------------------------------------
    def add_plan(self, asof: str, for_date: str, status: str, mode: str, payload: dict, note: str = "") -> int:
        return self.x("INSERT INTO plans(created_ts,asof,for_date,status,mode,payload,note) VALUES(?,?,?,?,?,?,?)",
                      (self.now(), asof, for_date, status, mode, json.dumps(payload, default=str), note))

    def plan(self, plan_id: int) -> dict | None:
        r = self.one("SELECT * FROM plans WHERE id=?", (plan_id,))
        if r:
            r["payload"] = json.loads(r["payload"])
        return r

    def latest_plan(self, statuses: tuple[str, ...] | None = None) -> dict | None:
        if statuses:
            r = self.one(f"SELECT id FROM plans WHERE status IN ({','.join('?' * len(statuses))}) "
                         f"ORDER BY id DESC LIMIT 1", statuses)
        else:
            r = self.one("SELECT id FROM plans ORDER BY id DESC LIMIT 1")
        return self.plan(r["id"]) if r else None

    def set_plan_status(self, plan_id: int, status: str, **cols) -> None:
        sets, args = ["status=?"], [status]
        for k, v in cols.items():
            if k not in ("approved_ts", "approved_by", "executed_ts", "note"):
                raise ValueError(k)
            sets.append(f"{k}=?"); args.append(v)
        self.x(f"UPDATE plans SET {','.join(sets)} WHERE id=?", (*args, plan_id))

    def update_plan_payload(self, plan_id: int, payload: dict) -> None:
        self.x("UPDATE plans SET payload=? WHERE id=?", (json.dumps(payload, default=str), plan_id))

    # ---- orders and fills ------------------------------------------------------------
    def add_order(self, *, plan_id: int | None, client_id: str, broker_id: str | None, symbol: str, side: str,
                  qty: float, kind: str, tif: str, status: str, raw: Any = None) -> None:
        self.x("INSERT OR IGNORE INTO orders(ts,plan_id,client_id,broker_id,symbol,side,qty,kind,tif,status,"
               "filled_qty,filled_avg,raw) VALUES(?,?,?,?,?,?,?,?,?,?,0,NULL,?)",
               (self.now(), plan_id, client_id, broker_id, symbol, side, qty, kind, tif, status,
                json.dumps(raw, default=str) if raw is not None else None))

    def order_exists(self, client_id: str) -> bool:
        return self.one("SELECT 1 FROM orders WHERE client_id=?", (client_id,)) is not None

    def update_order(self, client_id: str, **cols) -> None:
        allowed = {"broker_id", "status", "filled_qty", "filled_avg", "raw"}
        sets, args = [], []
        for k, v in cols.items():
            if k not in allowed:
                raise ValueError(k)
            sets.append(f"{k}=?"); args.append(json.dumps(v, default=str) if k == "raw" else v)
        if sets:
            self.x(f"UPDATE orders SET {','.join(sets)} WHERE client_id=?", (*args, client_id))

    def add_fill(self, client_id: str, symbol: str, side: str, qty: float, price: float, ts: str,
                 commission: float = 0.0) -> None:
        self.x("INSERT OR REPLACE INTO fills(ts,client_id,symbol,side,qty,price,commission) VALUES(?,?,?,?,?,?,?)",
               (ts, client_id, symbol, side, qty, price, commission))

    # ---- equity ----------------------------------------------------------------------
    def add_equity(self, session: str, equity: float, cash: float, gross: float, net: float, source: str) -> None:
        self.x("INSERT INTO equity(ts,session,equity,cash,gross,net,source) VALUES(?,?,?,?,?,?,?)",
               (self.now(), session, equity, cash, gross, net, source))

    def equity_by_session(self) -> list[dict]:
        """The LAST snapshot taken in each session, oldest first."""
        return self.q("SELECT e.* FROM equity e JOIN (SELECT session, MAX(id) mid FROM equity GROUP BY session) m "
                      "ON e.id=m.mid ORDER BY e.session")

    # ---- brackets, ideal weights, rebalances -----------------------------------------
    def set_bracket(self, symbol: str, side: str, qty: float, entry: float, stop: float, target: float,
                    order_id: str | None) -> None:
        self.x("INSERT INTO brackets(symbol,side,qty,entry,stop,target,set_ts,order_id) VALUES(?,?,?,?,?,?,?,?) "
               "ON CONFLICT(symbol) DO UPDATE SET side=excluded.side, qty=excluded.qty, entry=excluded.entry, "
               "stop=excluded.stop, target=excluded.target, set_ts=excluded.set_ts, order_id=excluded.order_id",
               (symbol, side, qty, entry, stop, target, self.now(), order_id))

    def brackets(self) -> dict[str, dict]:
        return {r["symbol"]: r for r in self.q("SELECT * FROM brackets")}

    def drop_bracket(self, symbol: str) -> None:
        self.x("DELETE FROM brackets WHERE symbol=?", (symbol,))

    def set_ideal(self, for_date: str, asof: str, weights: dict) -> None:
        self.x("INSERT INTO ideal(for_date,asof,weights,created_ts) VALUES(?,?,?,?) "
               "ON CONFLICT(for_date) DO UPDATE SET asof=excluded.asof, weights=excluded.weights, "
               "created_ts=excluded.created_ts", (for_date, asof, json.dumps(weights), self.now()))

    def ideal_weights(self) -> dict[str, dict]:
        return {r["for_date"]: json.loads(r["weights"]) for r in self.q("SELECT * FROM ideal ORDER BY for_date")}

    def mark_rebalance(self, asof: str) -> None:
        self.x("INSERT OR REPLACE INTO rebalances(asof,ts) VALUES(?,?)", (asof, self.now()))

    def last_rebalance(self) -> str | None:
        r = self.one("SELECT MAX(asof) a FROM rebalances")
        return r["a"] if r else None
