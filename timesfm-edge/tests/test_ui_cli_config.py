import http.client
import json
import re
import threading
import time
from pathlib import Path

import pytest
import yaml

from tfm_edge import cli
from tfm_edge.execution import engine
from tfm_edge.execution.config import load_bot_config
from tfm_edge.ui.server import HTML, serve

from .bot_harness import Sim


# ---- config ----------------------------------------------------------------------------------
def _write(tmp_path, **over):
    d = {"run_config": "config/run.yaml", "capital": 10000, "risk": {"max_capital": 10000},
         "broker": {"kind": "paper"}}
    d.update(over)
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "run.yaml").write_text(yaml.safe_dump({"name": "x", "data": {"source": "equity"}}))
    p = tmp_path / "config" / "bot.yaml"
    p.write_text(yaml.safe_dump(d))
    return p


def test_a_valid_config_loads_and_resolves_per_kind_ledgers(tmp_path):
    c = load_bot_config(_write(tmp_path), base_dir=tmp_path)
    assert c.capital == 10000 and c.db_path.endswith("state/paper/bot.sqlite")
    assert c.db_path_for("alpaca_live").endswith("state/alpaca_live/bot.sqlite")
    assert c.kill_file.endswith("state/KILL")                            # one kill file for every mode


def test_a_typo_in_a_risk_limit_is_an_error_not_a_silent_default(tmp_path):
    p = _write(tmp_path, risk={"max_capital": 10000, "daily_loss_limt": 0.001})
    with pytest.raises(ValueError, match="daily_loss_limt"):
        load_bot_config(p, base_dir=tmp_path)
    with pytest.raises(ValueError, match="unknown top-level"):
        load_bot_config(_write(tmp_path, captial=5), base_dir=tmp_path)


def test_max_capital_has_no_default(tmp_path):
    with pytest.raises(ValueError, match="max_capital is required"):
        load_bot_config(_write(tmp_path, risk={"daily_loss_limit": 0.01}), base_dir=tmp_path)


@pytest.mark.parametrize("over,needle", [
    (dict(capital=20000), "exceeds risk.max_capital"),
    (dict(broker={"kind": "binance"}), "broker.kind"),
    (dict(book={"top_fraction": 0.7}), "top_fraction"),
    (dict(risk={"max_capital": 10000, "daily_loss_limit": 5}), "daily_loss_limit"),
    (dict(risk={"max_capital": 10000, "max_gross_exposure": 0.5}), "below book.gross"),
])
def test_incoherent_configs_are_rejected(tmp_path, over, needle):
    with pytest.raises(ValueError, match=needle):
        load_bot_config(_write(tmp_path, **over), base_dir=tmp_path)


def test_the_shipped_configs_all_parse():
    root = Path(__file__).resolve().parents[1]
    for name in ("bot_paper.yaml", "bot_alpaca_paper.yaml", "bot_live.example.yaml"):
        load_bot_config(root / "config" / name, base_dir=root)


def test_the_live_example_does_not_enable_any_override_by_default():
    root = Path(__file__).resolve().parents[1]
    c = load_bot_config(root / "config" / "bot_live.example.yaml", base_dir=root)
    assert c.is_live and c.live.require_approval
    assert not c.live.acknowledge_gate_not_passed and not c.live.acknowledge_short_paper_run


# ---- the UI server ----------------------------------------------------------------------------
@pytest.fixture
def ui(tmp_path):
    sim = Sim(tmp_path, require_approval=True)
    srv = serve(sim.ctx, port=0, token="TESTTOKEN")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield sim, srv
    srv.shutdown()


def req(srv, method, path, body=None, headers=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{srv.server_port}", **(headers or {})}
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read()
    return r.status, (json.loads(raw) if r.getheader("Content-Type", "").startswith("application/json") else raw.decode())


def post(srv, action, body=None, token="TESTTOKEN", **kw):
    return req(srv, "POST", f"/api/{action}", body or {}, {"X-TFM-Token": token, **kw.pop("headers", {})}, **kw)


def wait_job(sim, srv, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = req(srv, "GET", "/api/state")[1]
        if not st["job_running"]:
            return st
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_server_binds_to_loopback_only(ui):
    _, srv = ui
    assert srv.server_address[0] == "127.0.0.1"


def test_page_embeds_the_token_and_state_is_served(ui):
    sim, srv = ui
    code, html = req(srv, "GET", "/")
    assert code == 200 and "TESTTOKEN" in html and "__TFM_TOKEN__" not in html
    code, st = req(srv, "GET", "/api/state")
    assert code == 200 and st["mode"] == "paper" and st["kill"] is None and st["account"]["equity"] == 100_000


def test_actions_without_the_token_are_refused(ui):
    sim, srv = ui
    for tok in ("", "wrong"):
        code, _ = post(srv, "kill", token=tok)
        assert code == 403
    assert engine.kill_state(sim.ctx) is None                              # nothing happened


def test_a_cross_site_request_cannot_press_the_kill_switch(ui):
    sim, srv = ui
    code, _ = post(srv, "kill", headers={"Origin": "https://evil.example"})
    assert code == 403 and engine.kill_state(sim.ctx) is None
    # even a page that somehow had the token is blocked by the origin check; a same-origin one passes
    code, _ = post(srv, "kill", headers={"Origin": f"http://127.0.0.1:{srv.server_port}"})
    assert code == 200 and engine.kill_state(sim.ctx)


def test_a_dns_rebinding_host_header_is_refused(ui):
    _, srv = ui
    assert req(srv, "GET", "/api/state", host="evil.example")[0] == 403
    assert req(srv, "GET", "/", host="evil.example:80")[0] == 403
    assert post(srv, "kill", host="attacker.test")[0] == 403


def test_get_cannot_change_state(ui):
    sim, srv = ui
    req(srv, "GET", "/api/kill"); req(srv, "GET", "/api/approve")
    assert engine.kill_state(sim.ctx) is None


def test_kill_and_resume_through_the_api(ui):
    sim, srv = ui
    assert post(srv, "kill", {"reason": "button"})[0] == 200
    st = req(srv, "GET", "/api/state")[1]
    assert st["kill"]["reason"] == "button"
    code, body = post(srv, "resume", {"confirm": "yes"})
    assert code == 400 and "RESUME" in body["error"]
    assert post(srv, "resume", {"confirm": "RESUME"})[0] == 200
    assert req(srv, "GET", "/api/state")[1]["kill"] is None


def test_plan_approve_execute_through_the_api(ui):
    sim, srv = ui
    sim.at(sim.evening())
    code, r = post(srv, "plan", {})
    assert code == 200 and r["ok"]
    st = wait_job(sim, srv)
    assert st["plan"]["status"] == "pending" and st["plan"]["n_orders"] > 0
    assert post(srv, "approve", {"plan_id": st["plan"]["id"]})[0] == 200
    sim.at(sim.morning())
    assert post(srv, "execute", {})[1]["ok"]
    st = wait_job(sim, srv)
    assert st["plan"]["status"] == "executed"


def test_only_one_long_task_runs_at_a_time(ui):
    sim, srv = ui
    gate = threading.Event()
    real = sim.ctx.load_panel
    sim.ctx.load_panel = lambda: (gate.wait(5), real())[1]
    sim.at(sim.evening())
    assert post(srv, "plan", {})[1]["ok"]
    code, r = post(srv, "plan", {})
    assert r["ok"] is False and "busy" in r["error"]
    gate.set(); wait_job(sim, srv)


def test_unknown_actions_and_bad_json_are_handled(ui):
    _, srv = ui
    assert post(srv, "format_disk")[0] == 404
    c = http.client.HTTPConnection("127.0.0.1", srv.server_port)
    c.request("POST", "/api/kill", body=b"{not json", headers={"Host": f"127.0.0.1:{srv.server_port}", "X-TFM-Token": "TESTTOKEN"})
    assert c.getresponse().status == 400


def test_the_page_never_parses_untrusted_text_as_html():
    src = HTML.read_text()
    for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert banned not in src, banned
    assert "textContent" in src


def test_a_hostile_string_in_the_ledger_is_data_not_markup(ui):
    sim, srv = ui
    sim.ctx.store.event("error", "broker", "<img src=x onerror=alert(1)>")
    st = req(srv, "GET", "/api/state")[1]
    assert any("<img" in e["message"] for e in st["events"])                # delivered as inert JSON text
    code, html = req(srv, "GET", "/")
    assert "onerror=alert" not in html                                     # and the page itself never contains it


# ---- the CLI -------------------------------------------------------------------------------------
def test_cli_plan_approve_execute_status_kill_resume(tmp_path, monkeypatch, capsys):
    sim = Sim(tmp_path, require_approval=True)
    monkeypatch.setattr(cli, "_ctx", lambda a: sim.ctx)
    sim.at(sim.evening())
    assert cli.main(["plan"]) == 0
    out = capsys.readouterr().out
    assert "PENDING" in out and "approve with" in out
    assert cli.main(["approve"]) == 0
    sim.at(sim.morning())
    assert cli.main(["execute"]) == 0
    assert cli.main(["status"]) == 0 and "trading: enabled" in capsys.readouterr().out
    assert cli.main(["kill", "--reason", "drill"]) == 0
    assert cli.main(["status"]) == 0 and "HALTED: drill" in capsys.readouterr().out
    assert cli.main(["resume", "--confirm", "nope"]) == 1
    assert cli.main(["resume", "--confirm", "RESUME"]) == 0


def test_cli_plan_reports_a_block_with_a_nonzero_exit(tmp_path, monkeypatch, capsys):
    sim = Sim(tmp_path)
    sim.ctx.load_panel = lambda: (_ for _ in ()).throw(ConnectionError("down"))
    monkeypatch.setattr(cli, "_ctx", lambda a: sim.ctx)
    sim.at(sim.evening())
    assert cli.main(["plan"]) == 2 and "blocked" in capsys.readouterr().out
