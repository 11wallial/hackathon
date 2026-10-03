"""Brokers: a paper simulator and an Alpaca adapter behind one interface.

PAPER FIRST (spec): PaperBroker needs no keys and no network. It fills at the next session's
open with the configured spread and slippage, charges commission, and simulates the exit
brackets from each session's high and low. AlpacaBroker talks to Alpaca's paper or live
endpoint; live is gated twice, once in construction and again before any order is written
(see engine.live_clearance).

WHAT IS NOT VERIFIED
--------------------
AlpacaBroker was written from Alpaca's documented REST API and tested against a stand-in
server that implements the same documented shapes. It has never spoken to the real service,
because the machine that built it had no route to the internet. The stand-in proves the
adapter is internally consistent, not that Alpaca behaves the way the stand-in does.
Run it against alpaca_paper first and read every order it places.
"""
from __future__ import annotations

import time as _time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

import requests

from ..config import CostModel
from .store import Store

OPEN_STATUSES = {"new", "accepted", "pending_new", "partially_filled", "held", "pending_cancel",
                 "pending_replace", "accepted_for_bidding", "calculated"}
ENTRY_PREFIX, EXIT_PREFIX = "tfm-e-", "tfm-x-"


class BrokerError(RuntimeError):
    pass


class LiveNotCleared(BrokerError):
    """A live order was attempted without the clearance checks having passed."""


@dataclass
class Account:
    equity: float
    cash: float
    buying_power: float = 0.0
    status: str = "ACTIVE"
    trading_blocked: bool = False
    shorting_enabled: bool = True
    pattern_day_trader: bool = False
    multiplier: float = 2.0


@dataclass
class Position:
    symbol: str
    qty: float                 # signed: negative is short
    avg_price: float
    market_value: float = 0.0
    current_price: float = 0.0


@dataclass
class BrokerOrder:
    id: str
    client_id: str
    symbol: str
    side: str
    qty: float
    kind: str                  # market | oco
    tif: str
    status: str
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    raw: dict = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


@dataclass
class AssetInfo:
    symbol: str
    tradable: bool = True
    shortable: bool = True
    easy_to_borrow: bool = True


class Broker(ABC):
    kind: str = "abstract"

    # ---- reads
    @abstractmethod
    def get_account(self) -> Account: ...
    @abstractmethod
    def get_positions(self) -> dict[str, Position]: ...
    @abstractmethod
    def get_open_orders(self) -> list[BrokerOrder]: ...
    @abstractmethod
    def asset_info(self, symbol: str) -> AssetInfo: ...
    @abstractmethod
    def get_orders_since(self, since_iso: str) -> list[BrokerOrder]: ...

    # ---- the one write that can add risk (live-gated)
    @abstractmethod
    def submit_order(self, symbol: str, side: str, qty: int, *, tif: str, client_id: str) -> BrokerOrder: ...

    # ---- writes that only reduce risk (always allowed)
    @abstractmethod
    def submit_exit_bracket(self, symbol: str, qty: int, close_side: str, stop: float, target: float,
                            client_id: str) -> BrokerOrder: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None: ...
    @abstractmethod
    def cancel_entry_orders(self) -> int: ...
    @abstractmethod
    def close_all_positions(self) -> int: ...

    def cancel_exit_for(self, symbol: str) -> int:
        n = 0
        for o in self.get_open_orders():
            if o.symbol == symbol and o.client_id.startswith(EXIT_PREFIX):
                self.cancel_order(o.id)
                n += 1
        return n


# =====================================================================================
class PaperBroker(Broker):
    """Local simulator whose state lives in the ledger, so it survives restarts."""
    kind = "paper"

    def __init__(self, store: Store, starting_cash: float, costs: CostModel, now_fn=None,
                 unshortable: set[str] | None = None):
        self.store, self.costs = store, costs
        self._now = now_fn or (lambda: datetime.now(timezone.utc))
        self.unshortable = set(unshortable or ())
        if self.store.get("paper.cash") is None:
            self.store.set("paper.cash", float(starting_cash))
            self.store.set("paper.positions", {})
            self.store.set("paper.orders", [])
            self.store.set("paper.marks", {})
            self.store.set("paper.start_cash", float(starting_cash))

    # state accessors -------------------------------------------------------------
    @property
    def cash(self) -> float: return self.store.get("paper.cash")
    def _pos(self) -> dict: return self.store.get("paper.positions", {})
    def _orders(self) -> list: return self.store.get("paper.orders", [])
    def _marks(self) -> dict: return self.store.get("paper.marks", {})

    def _to_order(self, o: dict) -> BrokerOrder:
        return BrokerOrder(id=o["id"], client_id=o["client_id"], symbol=o["symbol"], side=o["side"], qty=o["qty"],
                           kind=o["kind"], tif=o["tif"], status=o["status"], filled_qty=o.get("filled_qty", 0.0),
                           filled_avg_price=o.get("filled_avg"), raw=o)

    # reads -----------------------------------------------------------------------
    def get_positions(self):
        marks = self._marks()
        out = {}
        for s, p in self._pos().items():
            if p["qty"]:
                px = marks.get(s, p["avg"])
                out[s] = Position(s, p["qty"], p["avg"], p["qty"] * px, px)
        return out

    def get_account(self):
        pos = self.get_positions()
        mv = sum(p.market_value for p in pos.values())
        gross = sum(abs(p.market_value) for p in pos.values())
        eq = self.cash + mv
        return Account(equity=eq, cash=self.cash, buying_power=max(0.0, 2 * eq - gross))

    def get_open_orders(self):
        return [self._to_order(o) for o in self._orders() if o["status"] in OPEN_STATUSES]

    def get_orders_since(self, since_iso):
        return [self._to_order(o) for o in self._orders() if o["submitted_ts"] >= since_iso]

    def asset_info(self, symbol):
        return AssetInfo(symbol, True, symbol not in self.unshortable, symbol not in self.unshortable)

    # writes ----------------------------------------------------------------------
    def _add(self, o: dict) -> BrokerOrder:
        orders = self._orders()
        if any(x["client_id"] == o["client_id"] for x in orders):
            raise BrokerError(f"duplicate client_order_id {o['client_id']}")
        o.update(id=f"paper-{len(orders) + 1}", status="accepted", filled_qty=0.0, filled_avg=None,
                 submitted_ts=self._now().isoformat())
        orders.append(o)
        self.store.set("paper.orders", orders)
        return self._to_order(o)

    def submit_order(self, symbol, side, qty, *, tif, client_id):
        if side not in ("buy", "sell") or int(qty) != qty or qty <= 0:
            raise BrokerError(f"bad order {side} {qty}")
        pos = self._pos().get(symbol, {"qty": 0})["qty"]
        if side == "sell" and pos - qty < 0 and symbol in self.unshortable:
            raise BrokerError(f"{symbol} is not shortable")
        return self._add(dict(client_id=client_id, symbol=symbol, side=side, qty=int(qty), kind="market", tif=tif))

    def submit_exit_bracket(self, symbol, qty, close_side, stop, target, client_id):
        return self._add(dict(client_id=client_id, symbol=symbol, side=close_side, qty=int(qty), kind="oco",
                              tif="gtc", stop=float(stop), target=float(target)))

    def cancel_order(self, order_id):
        orders = self._orders()
        for o in orders:
            if o["id"] == order_id and o["status"] in OPEN_STATUSES:
                o["status"] = "canceled"
        self.store.set("paper.orders", orders)

    def cancel_entry_orders(self):
        orders, n = self._orders(), 0
        for o in orders:
            if o["status"] in OPEN_STATUSES and o["kind"] == "market":
                o["status"] = "canceled"; n += 1
        self.store.set("paper.orders", orders)
        return n

    def close_all_positions(self):
        n = 0
        marks = self._marks()
        for s, p in list(self._pos().items()):
            if p["qty"]:
                side = "sell" if p["qty"] > 0 else "buy"
                px = marks.get(s, p["avg"])
                self._apply_fill(None, s, side, abs(p["qty"]), px, self._now().isoformat(), slip=True)
                n += 1
        orders = self._orders()
        for o in orders:
            if o["status"] in OPEN_STATUSES:
                o["status"] = "canceled"
        self.store.set("paper.orders", orders)
        return n

    # settlement ------------------------------------------------------------------
    def _apply_fill(self, order: dict | None, symbol: str, side: str, qty: float, ref_px: float, ts: str,
                    slip: bool = True) -> float:
        slip_frac = (self.costs.half_spread_bps + self.costs.slippage_bps) / 1e4 if slip else 0.0
        px = ref_px * (1 + slip_frac) if side == "buy" else ref_px * (1 - slip_frac)
        commission = self.costs.commission_bps / 1e4 * px * qty
        signed = qty if side == "buy" else -qty
        pos = self._pos()
        cur = pos.get(symbol, {"qty": 0, "avg": 0.0})
        new_qty = cur["qty"] + signed
        if cur["qty"] == 0 or (cur["qty"] > 0) == (signed > 0):
            tot = abs(cur["qty"]) + qty
            avg = (cur["avg"] * abs(cur["qty"]) + px * qty) / tot if tot else px
        elif abs(signed) <= abs(cur["qty"]):
            avg = cur["avg"]                                         # reducing keeps the entry price
        else:
            avg = px                                                 # flipped through zero
        pos[symbol] = {"qty": new_qty, "avg": avg if new_qty else 0.0}
        cash = self.cash - signed * px - commission
        self.store.set("paper.positions", pos)
        self.store.set("paper.cash", cash)
        cid = order["client_id"] if order else f"paper-flatten-{symbol}-{ts}"
        self.store.add_fill(cid, symbol, side, qty, px, ts, commission)
        return px

    def settle_session(self, session: str, open_utc: datetime, bars: Mapping[str, Mapping[str, float]]) -> list[str]:
        """Fill everything that was working at this session's open, then test the exit brackets
        against the session's range. `bars`: symbol -> {open, high, low, close}."""
        log: list[str] = []
        orders = self._orders()
        ts = open_utc.isoformat()
        for o in orders:                                             # 1. market orders at the open
            if o["status"] != "accepted" or o["kind"] != "market" or o["submitted_ts"] >= ts:
                continue
            b = bars.get(o["symbol"])
            if b is None:
                continue                                             # no bar: stays working
            px = self._apply_fill(o, o["symbol"], o["side"], o["qty"], b["open"], ts)
            o.update(status="filled", filled_qty=o["qty"], filled_avg=px)
            log.append(f"{o['side']} {o['qty']} {o['symbol']} @ {px:.2f}")
        self.store.set("paper.orders", orders)
        orders = self._orders()
        for o in orders:                                             # 2. exit brackets over the session
            if o["status"] != "accepted" or o["kind"] != "oco" or o["submitted_ts"] >= ts:
                continue
            pos = self._pos().get(o["symbol"], {"qty": 0})["qty"]
            long_exit = o["side"] == "sell"
            if pos == 0 or (pos > 0) != long_exit or abs(pos) < o["qty"]:
                o["status"] = "canceled"; continue
            b = bars.get(o["symbol"])
            if b is None:
                continue
            fill = None
            if long_exit:
                if b["open"] <= o["stop"]: fill = b["open"]
                elif b["low"] <= o["stop"]: fill = o["stop"]
                elif b["open"] >= o["target"]: fill = b["open"]
                elif b["high"] >= o["target"]: fill = o["target"]
            else:
                if b["open"] >= o["stop"]: fill = b["open"]
                elif b["high"] >= o["stop"]: fill = o["stop"]
                elif b["open"] <= o["target"]: fill = b["open"]
                elif b["low"] <= o["target"]: fill = o["target"]
            if fill is not None:
                px = self._apply_fill(o, o["symbol"], o["side"], o["qty"], fill, ts)
                o.update(status="filled", filled_qty=o["qty"], filled_avg=px)
                log.append(f"EXIT {o['side']} {o['qty']} {o['symbol']} @ {px:.2f}")
        self.store.set("paper.orders", orders)
        marks = self._marks()
        marks.update({s: b["close"] for s, b in bars.items()})
        self.store.set("paper.marks", marks)
        self.store.set("paper.last_session", session)
        return log


# =====================================================================================
class AlpacaBroker(Broker):
    PAPER_URL, LIVE_URL = "https://paper-api.alpaca.markets", "https://api.alpaca.markets"

    def __init__(self, kind: str, key: str, secret: str, *, base_url: str | None = None,
                 session: requests.Session | None = None, timeout: float = 20.0):
        if kind not in ("alpaca_paper", "alpaca_live"):
            raise ValueError(kind)
        self.kind = kind
        self.base = (base_url or (self.LIVE_URL if kind == "alpaca_live" else self.PAPER_URL)).rstrip("/")
        self.s = session or requests.Session()
        self.s.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        self.timeout = timeout
        self.live_cleared = False          # set by the engine after live_clearance passes

    # plumbing --------------------------------------------------------------------
    def _req(self, method: str, path: str, *, params=None, json=None, retries: int = 0) -> Any:
        last: Exception | None = None
        for attempt in range(retries + 1):
            try:
                r = self.s.request(method, self.base + path, params=params, json=json, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as e:
                last = e
                if attempt < retries:
                    _time.sleep(0.5 * 2 ** attempt)
                    continue
                raise
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                _time.sleep(0.5 * 2 ** attempt)
                continue
            if r.status_code == 204 or not r.content:
                return None
            if r.status_code >= 400:
                raise BrokerError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
            return r.json()
        raise last or BrokerError("request failed")

    def _require_cleared(self) -> None:
        if self.kind == "alpaca_live" and not self.live_cleared:
            raise LiveNotCleared("live order refused: clearance checks have not passed in this process")

    @staticmethod
    def _f(x) -> float | None:
        return None if x in (None, "") else float(x)

    def _order(self, d: dict) -> BrokerOrder:
        kind = "oco" if d.get("order_class") == "oco" else d.get("type", "market")
        return BrokerOrder(id=d["id"], client_id=d.get("client_order_id", ""), symbol=d["symbol"], side=d["side"],
                           qty=float(d.get("qty") or 0), kind=kind, tif=d.get("time_in_force", ""),
                           status=d.get("status", ""), filled_qty=float(d.get("filled_qty") or 0),
                           filled_avg_price=self._f(d.get("filled_avg_price")), raw=d)

    # reads -----------------------------------------------------------------------
    def get_account(self):
        a = self._req("GET", "/v2/account", retries=2)
        return Account(equity=float(a["equity"]), cash=float(a["cash"]), buying_power=float(a.get("buying_power") or 0),
                       status=a.get("status", ""), trading_blocked=bool(a.get("trading_blocked") or a.get("account_blocked")),
                       shorting_enabled=bool(a.get("shorting_enabled", False)),
                       pattern_day_trader=bool(a.get("pattern_day_trader", False)),
                       multiplier=float(a.get("multiplier") or 1))

    def get_positions(self):
        out = {}
        for p in self._req("GET", "/v2/positions", retries=2) or []:
            q = float(p["qty"])
            if p.get("side") == "short" and q > 0:
                q = -q                                               # normalise: negative is short
            out[p["symbol"]] = Position(p["symbol"], q, float(p["avg_entry_price"]),
                                        float(p.get("market_value") or 0), float(p.get("current_price") or 0))
        return out

    def get_open_orders(self):
        rows = self._req("GET", "/v2/orders", params={"status": "open", "limit": 500, "nested": "true"}, retries=2)
        return [self._order(d) for d in rows or []]

    def get_orders_since(self, since_iso):
        rows = self._req("GET", "/v2/orders", params={"status": "all", "after": since_iso, "limit": 500,
                                                      "direction": "asc", "nested": "true"}, retries=2)
        return [self._order(d) for d in rows or []]

    def asset_info(self, symbol):
        a = self._req("GET", f"/v2/assets/{symbol}", retries=2)
        return AssetInfo(symbol, bool(a.get("tradable")), bool(a.get("shortable")), bool(a.get("easy_to_borrow")))

    # writes that add risk --------------------------------------------------------
    def _post_order(self, body: dict) -> BrokerOrder:
        """POST an order idempotently. If the request times out we do NOT know whether Alpaca
        received it; resending could double the position. So look the order up by its client id
        first, and only treat it as unsent if Alpaca has never heard of it."""
        try:
            return self._order(self._req("POST", "/v2/orders", json=body))
        except (requests.ConnectionError, requests.Timeout):
            try:
                found = self._req("GET", "/v2/orders:by_client_order_id",
                                  params={"client_order_id": body["client_order_id"]}, retries=2)
                if found:
                    return self._order(found)
            except BrokerError:
                pass
            raise BrokerError(f"order {body['client_order_id']} timed out and could not be confirmed either "
                              f"way; check the account before retrying")

    def submit_order(self, symbol, side, qty, *, tif, client_id):
        self._require_cleared()
        if side not in ("buy", "sell") or int(qty) != qty or qty <= 0:
            raise BrokerError(f"bad order {side} {qty}")
        return self._post_order({"symbol": symbol, "qty": str(int(qty)), "side": side, "type": "market",
                                 "time_in_force": tif, "client_order_id": client_id})

    def submit_exit_bracket(self, symbol, qty, close_side, stop, target, client_id):
        # A protective exit only ever REDUCES an existing position, so it is deliberately not
        # behind the live clearance: failing clearance must never leave a position unprotected.
        return self._post_order({"symbol": symbol, "qty": str(int(qty)), "side": close_side, "type": "limit",
                                 "time_in_force": "gtc", "order_class": "oco",
                                 "take_profit": {"limit_price": f"{target:.2f}"},
                                 "stop_loss": {"stop_price": f"{stop:.2f}"}, "client_order_id": client_id})

    # writes that reduce risk -----------------------------------------------------
    def cancel_order(self, order_id):
        self._req("DELETE", f"/v2/orders/{order_id}")

    def cancel_entry_orders(self):
        n = 0
        for o in self.get_open_orders():
            if not o.client_id.startswith(EXIT_PREFIX):
                self.cancel_order(o.id)
                n += 1
        return n

    def close_all_positions(self):
        before = len(self.get_positions())
        self._req("DELETE", "/v2/positions", params={"cancel_orders": "true"})
        return before
