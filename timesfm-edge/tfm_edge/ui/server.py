"""A small local control panel. Standard library only.

SECURITY MODEL (this page can approve orders and trade real money, so it is not casual)
  - binds to 127.0.0.1 only. For another machine, use an SSH tunnel; there is no remote mode.
  - every state-changing request needs a per-process random token, which is embedded in the page
    it serves. A different website open in your browser cannot read that token, so it cannot make
    your browser approve a plan or press the kill switch (CSRF).
  - the Host header must be the loopback address on our port, which defeats DNS rebinding.
  - the page builds its DOM with textContent, never innerHTML, so a hostile string arriving in a
    broker error or a symbol name cannot inject script.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..execution import engine
from ..execution.engine import Context
from ..execution.preflight import run_preflight, verdict
from ..execution.sessions import to_et

HTML = Path(__file__).with_name("index.html")


class Jobs:
    """One long task at a time. Planning with a real model can take minutes, so it must not hold
    an HTTP request open, and the engine is not safe to run concurrently with itself."""
    def __init__(self):
        self._lock, self._n, self.current, self.last = threading.Lock(), 0, None, None

    def start(self, name: str, fn) -> dict:
        if not self._lock.acquire(blocking=False):
            return {"ok": False, "error": f"busy: {self.current['name']} is still running"}
        self._n += 1
        job = {"id": self._n, "name": name, "status": "running", "started": datetime.now(timezone.utc).isoformat()}
        self.current = job

        def run():
            try:
                job["result"] = fn()
                job["status"] = "done"
            except Exception as e:
                job["status"] = "error"
                job["error"] = f"{type(e).__name__}: {e}"
            finally:
                job["finished"] = datetime.now(timezone.utc).isoformat()
                self.last, self.current = job, None
                self._lock.release()
        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "job": job}


def _plan_view(p: dict | None) -> dict | None:
    if not p:
        return None
    pl = p["payload"]
    return {"id": p["id"], "status": p["status"], "asof": p["asof"], "for_date": p["for_date"], "mode": p["mode"],
            "created_ts": p["created_ts"], "approved_by": p["approved_by"], "note": p["note"],
            "orders": pl.get("orders", [])[:80], "n_orders": len(pl.get("orders", [])),
            "gross_traded": sum(o["notional"] for o in pl.get("orders", [])),
            "decision": pl.get("decision"), "violations": pl.get("violations", []), "reasons": pl.get("reasons", []),
            "top": pl.get("top", []), "bottom": pl.get("bottom", []), "capital": pl.get("capital"),
            "coverage": pl.get("coverage"), "model": pl.get("model"), "fingerprint": pl.get("fingerprint")}


class App:
    def __init__(self, ctx: Context, jobs: Jobs | None = None):
        self.ctx, self.jobs = ctx, jobs or Jobs()

    def state(self) -> dict:
        c, st = self.ctx, self.ctx.store
        out: dict = {"name": c.cfg.name, "mode": c.cfg.broker.kind, "is_live": c.cfg.is_live,
                     "capital": c.cfg.capital, "now_et": to_et(c.now()).strftime("%a %Y-%m-%d %H:%M ET"),
                     "require_approval": c.cfg.live.require_approval,
                     "kill": engine.kill_state(c), "model": c.run.forecast.model_id if c.run.forecast.forecaster == "timesfm" else c.run.forecast.forecaster,
                     "risk": {"max_capital": c.cfg.risk.max_capital, "daily_loss_limit": c.cfg.risk.daily_loss_limit,
                              "max_drawdown_halt": c.cfg.risk.max_drawdown_halt, "max_gross": c.cfg.risk.max_gross_exposure,
                              "max_net": c.cfg.risk.max_net_exposure, "max_name": c.cfg.risk.max_name_weight,
                              "stop_mult": c.cfg.risk.stop_vol_mult, "target_mult": c.cfg.risk.target_vol_mult,
                              "flatten_on_halt": c.cfg.risk.flatten_on_halt}}
        out["clearance"] = [{"name": k.name, "status": k.status, "detail": k.detail} for k in engine.live_clearance(c)]
        try:
            a = c.broker.get_account()
            out["account"] = {"equity": a.equity, "cash": a.cash, "buying_power": a.buying_power, "status": a.status}
            brk = st.brackets()
            pos = []
            for s, p in sorted(engine._positions(c).items()):
                b = brk.get(s)
                px = p.current_price or p.avg_price
                pos.append({"symbol": s, "qty": p.qty, "avg": p.avg_price, "price": px, "value": p.market_value,
                            "weight": p.market_value / max(c.cfg.capital, 1), "pnl": (px - p.avg_price) * p.qty,
                            "stop": b["stop"] if b else None, "target": b["target"] if b else None})
            out["positions"] = pos
        except Exception as e:
            out["account"] = None
            out["positions"] = []
            out["broker_error"] = f"{type(e).__name__}: {e}"
        out["plan"] = _plan_view(st.latest_plan())
        out["plans"] = [{"id": r["id"], "asof": r["asof"], "for_date": r["for_date"], "status": r["status"]}
                        for r in st.q("SELECT id,asof,for_date,status FROM plans ORDER BY id DESC LIMIT 10")]
        out["equity"] = [{"session": e["session"], "equity": e["equity"]} for e in st.equity_by_session()][-120:]
        out["divergence"] = st.get("divergence.latest")
        out["events"] = [{"ts": e["ts"], "level": e["level"], "kind": e["kind"], "message": e["message"]}
                         for e in st.events(40)]
        out["job"] = self.jobs.current or self.jobs.last
        out["job_running"] = self.jobs.current is not None
        return out

    # ---- actions ---------------------------------------------------------------------------
    def do(self, action: str, body: dict) -> dict:
        c = self.ctx
        if action == "kill":
            return {"ok": True, **engine.kill(c, body.get("reason") or "kill switch pressed in the UI",
                                              flatten=bool(body.get("flatten")), by="ui")}
        if action == "resume":
            engine.resume(c, body.get("confirm", ""), by="ui")
            return {"ok": True}
        if action == "approve":
            engine.approve(c, int(body["plan_id"]), by="ui")
            return {"ok": True}
        if action == "reject":
            engine.reject(c, int(body["plan_id"]), by="ui")
            return {"ok": True}
        if action == "plan":
            return self.jobs.start("plan", lambda: _slim(engine.plan(c, force=bool(body.get("force")))))
        if action == "reconcile":
            return self.jobs.start("reconcile", lambda: engine.reconcile(c))
        if action == "execute":
            return self.jobs.start("execute", lambda: engine.execute(c))
        if action == "preflight":
            def go():
                checks = run_preflight(c)
                c.store.set("preflight.latest", {"verdict": verdict(checks), "ts": c.store.now(),
                                                 "checks": [vars(k) for k in checks]})
                return {"verdict": verdict(checks), "checks": [vars(k) for k in checks]}
            return self.jobs.start("preflight", go)
        raise KeyError(action)


def _slim(p: dict) -> dict:
    return {"plan_id": p["id"], "status": p["status"], "note": p["note"]}


def make_handler(app: App, token: str):
    class H(BaseHTTPRequestHandler):
        server_version = "tfm-ui"

        @property
        def allowed_hosts(self) -> set[str]:
            p = self.server.server_port                                   # the port actually bound
            return {f"127.0.0.1:{p}", f"localhost:{p}"}

        def _send(self, code: int, body: bytes, ctype: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; "
                                                         "script-src 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj):
            self._send(code, json.dumps(obj, default=str).encode())

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in self.allowed_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._json(403, {"error": "bad host header"})
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                html = HTML.read_text().replace("__TFM_TOKEN__", token)
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path == "/api/state":
                try:
                    return self._json(200, app.state())
                except Exception as e:
                    return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return self._json(403, {"error": "bad host header"})
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{h}" for h in self.allowed_hosts}:
                return self._json(403, {"error": "bad origin"})
            if not secrets.compare_digest(self.headers.get("X-TFM-Token", ""), token):
                return self._json(403, {"error": "missing or wrong token"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > 100_000:
                return self._json(413, {"error": "too large"})
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json(400, {"error": "bad json"})
            action = self.path.rsplit("/", 1)[-1]
            try:
                return self._json(200, app.do(action, body))
            except KeyError:
                return self._json(404, {"error": f"unknown action {action}"})
            except (ValueError, RuntimeError) as e:
                return self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:
                return self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

        def log_message(self, *a):
            pass

    return H


def serve(ctx: Context, port: int = 8765, token: str | None = None, jobs: Jobs | None = None):
    token = token or secrets.token_urlsafe(24)
    app = App(ctx, jobs)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, token))
    srv.token, srv.app = token, app                                 # type: ignore[attr-defined]
    return srv
