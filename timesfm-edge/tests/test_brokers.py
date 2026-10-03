import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from tfm_edge.config import CostModel
from tfm_edge.execution.broker import (AlpacaBroker, BrokerError, LiveNotCleared, PaperBroker)
from tfm_edge.execution.store import Store

NO_COST = CostModel(0.0, 0.0, 0.0)
COSTS = CostModel(0.2, 0.8, 0.5)
T0 = datetime(2026, 3, 2, 21, 0, tzinfo=timezone.utc)            # the evening before the session
OPEN = datetime(2026, 3, 3, 14, 30, tzinfo=timezone.utc)         # 09:30 ET the next day


def _pb(cash=10_000.0, costs=NO_COST, **kw):
    return PaperBroker(Store(":memory:"), cash, costs, now_fn=lambda: T0, **kw)


def bar(o, h=None, l=None, c=None):
    return {"open": o, "high": h or o * 1.01, "low": l or o * 0.99, "close": c or o}


# ---- PaperBroker ----------------------------------------------------------------------
def test_buy_fills_at_the_open_not_before():
    b = _pb()
    b.submit_order("AAA", "buy", 10, tif="opg", client_id="e1")
    assert b.get_positions() == {}                                 # nothing happens until a session settles
    b.settle_session("2026-03-03", OPEN, {"AAA": bar(100, c=105)})
    p = b.get_positions()["AAA"]
    assert p.qty == 10 and p.avg_price == 100 and p.current_price == 105
    assert b.get_account().equity == pytest.approx(10_000 + 10 * 5)


def test_slippage_and_commission_are_charged():
    b = _pb(costs=COSTS)
    b.submit_order("AAA", "buy", 100, tif="opg", client_id="e1")
    b.settle_session("2026-03-03", OPEN, {"AAA": bar(100, c=100)})
    slip = (0.8 + 0.5) / 1e4
    fill = b.get_positions()["AAA"].avg_price
    assert fill == pytest.approx(100 * (1 + slip))
    cost = 100 * 100 * slip + 0.2 / 1e4 * fill * 100
    assert b.get_account().equity == pytest.approx(10_000 - cost, rel=1e-6)


def test_shorts_and_equity_identity():
    b = _pb()
    b.submit_order("AAA", "sell", 20, tif="opg", client_id="s1")
    b.submit_order("BBB", "buy", 10, tif="opg", client_id="b1")
    b.settle_session("2026-03-03", OPEN, {"AAA": bar(50, c=48), "BBB": bar(100, c=101)})
    pos = b.get_positions()
    assert pos["AAA"].qty == -20 and pos["BBB"].qty == 10
    a = b.get_account()
    assert a.equity == pytest.approx(a.cash + sum(p.market_value for p in pos.values()))
    assert a.equity == pytest.approx(10_000 + 20 * 2 + 10 * 1)     # short gained 2/share, long gained 1/share


def test_partial_reduce_keeps_entry_price_and_flip_resets_it():
    b = _pb()
    b.submit_order("AAA", "buy", 10, tif="opg", client_id="1")
    b.settle_session("2026-03-03", OPEN, {"AAA": bar(100)})
    b.submit_order("AAA", "sell", 4, tif="opg", client_id="2")
    b.settle_session("2026-03-04", OPEN + timedelta(days=1), {"AAA": bar(110)})
    assert b.get_positions()["AAA"].qty == 6 and b.get_positions()["AAA"].avg_price == 100


def test_duplicate_client_id_is_refused():
    b = _pb()
    b.submit_order("AAA", "buy", 1, tif="opg", client_id="same")
    with pytest.raises(BrokerError, match="duplicate"):
        b.submit_order("AAA", "buy", 1, tif="opg", client_id="same")


def test_bad_orders_are_refused():
    b = _pb()
    for args in [("AAA", "buy", 0), ("AAA", "buy", -3), ("AAA", "hold", 1), ("AAA", "buy", 1.5)]:
        with pytest.raises(BrokerError):
            b.submit_order(*args, tif="opg", client_id=f"x{args}")


def test_order_submitted_after_the_open_waits_for_the_next_session():
    late = PaperBroker(Store(":memory:"), 10_000, NO_COST, now_fn=lambda: OPEN + timedelta(hours=1))
    late.submit_order("AAA", "buy", 5, tif="day", client_id="late")
    late.settle_session("2026-03-03", OPEN, {"AAA": bar(100)})
    assert late.get_positions() == {}                              # missed that open
    late.settle_session("2026-03-04", OPEN + timedelta(days=1), {"AAA": bar(101)})
    assert late.get_positions()["AAA"].qty == 5


def test_stop_fills_at_the_stop_and_gaps_fill_at_the_open():
    for open_, low, expect in [(100, 93, 94.0), (90, 88, 90.0)]:     # intraday touch, then a gap through
        b = _pb()
        b.submit_order("AAA", "buy", 10, tif="opg", client_id="e")
        b.settle_session("2026-03-03", OPEN, {"AAA": bar(100)})
        b.submit_exit_bracket("AAA", 10, "sell", stop=94.0, target=106.0, client_id="x")
        # the exit was submitted at T0, before the next open, so it is live for that session
        b.settle_session("2026-03-04", OPEN + timedelta(days=1), {"AAA": bar(open_, h=open_ * 1.01, l=low)})
        assert "AAA" not in b.get_positions()
        assert b.get_account().equity == pytest.approx(10_000 + 10 * (expect - 100))


def test_target_fills_and_a_bracket_without_a_position_is_cancelled():
    b = _pb()
    b.submit_order("AAA", "buy", 10, tif="opg", client_id="e")
    b.settle_session("2026-03-03", OPEN, {"AAA": bar(100)})
    b.submit_exit_bracket("AAA", 10, "sell", stop=94.0, target=106.0, client_id="x")
    b.settle_session("2026-03-04", OPEN + timedelta(days=1), {"AAA": bar(101, h=107, l=100)})
    assert "AAA" not in b.get_positions()
    assert b.get_account().equity == pytest.approx(10_000 + 10 * 6)
    b.submit_exit_bracket("AAA", 10, "sell", stop=94.0, target=106.0, client_id="x2")
    b.settle_session("2026-03-05", OPEN + timedelta(days=2), {"AAA": bar(101)})
    assert b.get_open_orders() == []                               # cancelled, not left dangling


def test_close_all_and_cancel_entries_but_not_exits():
    b = _pb()
    b.submit_order("AAA", "buy", 10, tif="opg", client_id="e")
    b.settle_session("2026-03-03", OPEN, {"AAA": bar(100)})
    b.submit_exit_bracket("AAA", 10, "sell", stop=94.0, target=106.0, client_id="x")
    b.submit_order("BBB", "buy", 5, tif="opg", client_id="e2")
    assert b.cancel_entry_orders() == 1
    assert [o.client_id for o in b.get_open_orders()] == ["x"]     # the protective exit survives a halt
    assert b.close_all_positions() == 1 and b.get_positions() == {}


def test_state_survives_a_restart():
    store = Store(":memory:")
    b1 = PaperBroker(store, 10_000, NO_COST, now_fn=lambda: T0)
    b1.submit_order("AAA", "buy", 10, tif="opg", client_id="e")
    b1.settle_session("2026-03-03", OPEN, {"AAA": bar(100)})
    b2 = PaperBroker(store, 999_999, NO_COST, now_fn=lambda: T0)    # a different starting cash must be ignored
    assert b2.get_positions()["AAA"].qty == 10 and b2.get_account().equity == pytest.approx(10_000)


def test_unshortable_names_are_refused_on_open_short():
    b = _pb(unshortable={"HTB"})
    assert b.asset_info("HTB").shortable is False and b.asset_info("OK").shortable
    with pytest.raises(BrokerError, match="shortable"):
        b.submit_order("HTB", "sell", 1, tif="opg", client_id="s")


# ---- AlpacaBroker against a stand-in server -------------------------------------------
class Fake:
    """In-memory model of the documented Alpaca REST shapes. Proves the adapter is
    self-consistent. It does NOT prove Alpaca behaves like this."""
    def __init__(self):
        self.orders, self.positions, self.drop_reply_for = [], {}, set()
        self.calls = []


FAKE = Fake()


class H(BaseHTTPRequestHandler):
    def _send(self, code, body=None):
        raw = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _route(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        FAKE.calls.append((self.command, u.path, q, body))
        if self.headers.get("APCA-API-KEY-ID") != "KEY":
            return self._send(401, {"message": "forbidden"})
        m, p = self.command, u.path
        if m == "GET" and p == "/v2/account":
            return self._send(200, {"equity": "10000.5", "cash": "9000", "buying_power": "20000", "status": "ACTIVE",
                                    "trading_blocked": False, "account_blocked": False, "shorting_enabled": True,
                                    "pattern_day_trader": False, "multiplier": "2"})
        if m == "GET" and p == "/v2/positions":
            return self._send(200, list(FAKE.positions.values()))
        if m == "DELETE" and p == "/v2/positions":
            FAKE.positions.clear()
            return self._send(207, [])
        if m == "GET" and p.startswith("/v2/assets/"):
            sym = p.rsplit("/", 1)[1]
            return self._send(200, {"symbol": sym, "tradable": True, "shortable": sym != "HTB",
                                    "easy_to_borrow": sym != "HTB"})
        if p == "/v2/orders:by_client_order_id":
            for o in FAKE.orders:
                if o["client_order_id"] == q["client_order_id"]:
                    return self._send(200, o)
            return self._send(404, {"message": "order not found"})
        if m == "POST" and p == "/v2/orders":
            if any(o["client_order_id"] == body["client_order_id"] for o in FAKE.orders):
                return self._send(422, {"message": "client_order_id must be unique"})
            o = dict(body, id=f"id-{len(FAKE.orders) + 1}", status="accepted", filled_qty="0",
                     filled_avg_price=None)
            FAKE.orders.append(o)
            if body["client_order_id"] in FAKE.drop_reply_for:
                self.connection.close()                  # processed, but the reply never arrives
                return
            return self._send(200, o)
        if m == "GET" and p == "/v2/orders":
            rows = [o for o in FAKE.orders if q.get("status") != "open" or o["status"] in ("accepted", "new")]
            return self._send(200, rows)
        if m == "DELETE" and p.startswith("/v2/orders/"):
            oid = p.rsplit("/", 1)[1]
            for o in FAKE.orders:
                if o["id"] == oid:
                    o["status"] = "canceled"
            return self._send(204)
        return self._send(404, {"message": f"no route {m} {p}"})

    do_GET = do_POST = do_DELETE = _route

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def alpaca_url():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def ab(alpaca_url):
    FAKE.__init__()
    return AlpacaBroker("alpaca_paper", "KEY", "SECRET", base_url=alpaca_url, timeout=3.0)


def test_alpaca_reads_parse(ab):
    FAKE.positions = {
        "AAA": {"symbol": "AAA", "qty": "10", "side": "long", "avg_entry_price": "50", "market_value": "520", "current_price": "52"},
        "BBB": {"symbol": "BBB", "qty": "5", "side": "short", "avg_entry_price": "20", "market_value": "-95", "current_price": "19"},
    }
    a = ab.get_account()
    assert a.equity == 10000.5 and a.shorting_enabled and not a.trading_blocked
    pos = ab.get_positions()
    assert pos["AAA"].qty == 10 and pos["BBB"].qty == -5          # short normalised to negative
    assert ab.asset_info("HTB").shortable is False and ab.asset_info("OK").shortable


def test_alpaca_bad_credentials_surface_as_broker_error(alpaca_url):
    bad = AlpacaBroker("alpaca_paper", "WRONG", "S", base_url=alpaca_url)
    with pytest.raises(BrokerError, match="401"):
        bad.get_account()


def test_alpaca_order_payloads(ab):
    ab.submit_order("AAA", "buy", 7, tif="opg", client_id="tfm-e-1-AAA")
    ab.submit_exit_bracket("AAA", 7, "sell", stop=94.126, target=106.004, client_id="tfm-x-1-AAA")
    posts = [c[3] for c in FAKE.calls if c[0] == "POST"]
    assert posts[0] == {"symbol": "AAA", "qty": "7", "side": "buy", "type": "market", "time_in_force": "opg",
                        "client_order_id": "tfm-e-1-AAA"}
    oco = posts[1]
    assert oco["order_class"] == "oco" and oco["time_in_force"] == "gtc" and oco["type"] == "limit"
    assert oco["stop_loss"] == {"stop_price": "94.13"} and oco["take_profit"] == {"limit_price": "106.00"}
    assert oco["qty"] == "7" and oco["side"] == "sell"


def test_alpaca_duplicate_client_id_is_rejected_not_resubmitted(ab):
    ab.submit_order("AAA", "buy", 1, tif="opg", client_id="tfm-e-dup")
    with pytest.raises(BrokerError, match="422"):
        ab.submit_order("AAA", "buy", 1, tif="opg", client_id="tfm-e-dup")
    assert len(FAKE.orders) == 1


def test_lost_reply_does_not_double_the_order(ab):
    """The dangerous case: Alpaca got the order but the reply was lost. Retrying blindly
    would buy twice. The adapter must find the first order by its client id instead."""
    FAKE.drop_reply_for = {"tfm-e-lost"}
    o = ab.submit_order("AAA", "buy", 3, tif="opg", client_id="tfm-e-lost")
    assert o.client_id == "tfm-e-lost" and len([x for x in FAKE.orders if x["client_order_id"] == "tfm-e-lost"]) == 1
    assert len([c for c in FAKE.calls if c[0] == "POST"]) == 1


def test_cancel_entries_leaves_protective_exits_alone(ab):
    ab.submit_order("AAA", "buy", 1, tif="opg", client_id="tfm-e-1")
    ab.submit_order("BBB", "buy", 1, tif="opg", client_id="tfm-e-2")
    ab.submit_exit_bracket("CCC", 1, "sell", 90, 110, client_id="tfm-x-1")
    assert ab.cancel_entry_orders() == 2
    assert [o.client_id for o in ab.get_open_orders()] == ["tfm-x-1"]


def test_live_broker_refuses_risk_adding_orders_until_cleared(alpaca_url):
    live = AlpacaBroker("alpaca_live", "KEY", "S", base_url=alpaca_url)
    with pytest.raises(LiveNotCleared):
        live.submit_order("AAA", "buy", 1, tif="opg", client_id="e")
    FAKE.__init__()
    live.cancel_entry_orders()                       # reducing risk never needs clearance...
    live.close_all_positions()
    # ...and neither does a protective exit, which can only shrink a position
    assert live.submit_exit_bracket("AAA", 1, "sell", 90, 110, client_id="tfm-x-1").kind == "oco"
    FAKE.__init__()
    live.live_cleared = True
    assert live.submit_order("AAA", "buy", 1, tif="opg", client_id="e").symbol == "AAA"


def test_live_url_is_the_real_one_unless_overridden():
    assert AlpacaBroker("alpaca_live", "k", "s").base == "https://api.alpaca.markets"
    assert AlpacaBroker("alpaca_paper", "k", "s").base == "https://paper-api.alpaca.markets"
