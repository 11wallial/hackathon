"""python -m tfm_edge <command> --config config/bot_paper.yaml

  preflight   GO / NO-GO checklist: network, data, model, account, live clearance
  plan        decide today's trades and write a plan (places no orders)
  approve     approve a pending plan            (approve [ID])
  reject      reject a plan                     (reject [ID])
  execute     submit the approved plan's orders (normally the daemon does this at 09:00 ET)
  reconcile   record fills, snapshot equity, place protective brackets, check limits
  status      one-screen summary
  report      write the live-vs-ideal-vs-backtest divergence report
  kill        halt trading                      (kill [--flatten] [--reason TEXT])
  resume      lift a halt                       (resume --confirm RESUME)
  daemon      run the scheduler: reconcile, plan, execute at the right times
  ui          local control panel on http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .execution import engine
from .execution.broker import BrokerError
from .execution.config import load_bot_config
from .execution.preflight import run_preflight, verdict


def _ctx(args):
    cfg = load_bot_config(args.config)
    return engine.build_context(cfg)


def cmd_preflight(a):
    ctx = _ctx(a)
    checks = run_preflight(ctx)
    for c in checks:
        print(c)
    v = verdict(checks)
    print(f"\n==> {v}" + ("" if v == "GO" else "  (resolve every [FAIL] before going further)"))
    return 0 if v == "GO" else 1


def cmd_plan(a):
    ctx = _ctx(a)
    p = engine.plan(ctx, force=a.force)
    pl = p["payload"]
    print(f"plan {p['id']}: {p['status'].upper()}  decided on {p['asof']} close, trades at {p['for_date']} open")
    if p["status"] == "blocked":
        print("  blocked: " + (p["note"] or "see events"))
        return 2
    d = pl["decision"]
    print(f"  {d['n_long']} long / {d['n_short']} short, gross {d['gross']:.2f}, net {d['net']:+.2f}, "
          f"turnover {d['turnover']:.1%}, {len(pl['orders'])} orders, capital ${pl['capital']:,.0f}")
    for n in d["notes"]:
        print(f"  - {n}")
    for o in pl["orders"][:20]:
        print(f"    {o['side']:4} {o['qty']:>5} {o['symbol']:<6} ~${o['notional']:>9,.0f}   {o['from']:+d} -> {o['to']:+d}")
    if len(pl["orders"]) > 20:
        print(f"    ... and {len(pl['orders']) - 20} more")
    if p["status"] == "pending":
        print(f"\n  approve with:  python -m tfm_edge approve {p['id']} --config {a.config}")
    return 0


def cmd_approve(a):
    ctx = _ctx(a)
    pid = a.plan_id or (ctx.store.latest_plan(("pending",)) or {}).get("id")
    if not pid:
        print("no pending plan"); return 1
    engine.approve(ctx, pid, by="cli"); print(f"plan {pid} approved"); return 0


def cmd_reject(a):
    ctx = _ctx(a)
    pid = a.plan_id or (ctx.store.latest_plan(("pending", "approved")) or {}).get("id")
    if not pid:
        print("no plan to reject"); return 1
    engine.reject(ctx, pid, by="cli"); print(f"plan {pid} rejected"); return 0


def cmd_execute(a):
    r = engine.execute(_ctx(a)); print(r); return 0 if r["status"] in ("executed", "no_approved_plan") else 2


def cmd_reconcile(a):
    r = engine.reconcile(_ctx(a)); print({k: v for k, v in r.items() if k != "fills"}); return 0


def cmd_status(a):
    ctx = _ctx(a)
    k = engine.kill_state(ctx)
    acct = ctx.broker.get_account()
    pos = engine._positions(ctx)
    print(f"{ctx.cfg.name}  [{ctx.cfg.broker.kind}]  capital ${ctx.cfg.capital:,.0f}  equity ${acct.equity:,.2f}")
    print(f"  trading: {'HALTED: ' + k['reason'] if k else 'enabled'}")
    print(f"  positions: {len(pos)} ({sum(1 for p in pos.values() if p.qty > 0)}L/{sum(1 for p in pos.values() if p.qty < 0)}S), "
          f"brackets on {len(ctx.store.brackets())}")
    p = ctx.store.latest_plan()
    if p:
        print(f"  latest plan: #{p['id']} {p['status']} ({p['asof']} -> {p['for_date']}), {len(p['payload'].get('orders', []))} orders")
    for c in engine.live_clearance(ctx):
        print(f"  {c}")
    return 0


def cmd_report(a):
    ctx = _ctx(a)
    panel = ctx.load_panel()
    r = engine.refresh_divergence(ctx, panel)
    if r is None:
        print("could not compute (see events)"); return 1
    print(f"{r['n']} sessions compared" + (f"; mean gap {r['mean_gap_bps']:+.2f} bps/day, z {r.get('z_gap')}" if r["n"] else f"; {r.get('note')}"))
    return 0


def cmd_kill(a):
    ctx = _ctx(a)
    print(engine.kill(ctx, a.reason, flatten=a.flatten, by="cli")); return 0


def cmd_resume(a):
    ctx = _ctx(a)
    try:
        engine.resume(ctx, a.confirm or "", by="cli")
    except (ValueError, RuntimeError) as e:
        print(f"refused: {e}"); return 1
    print("trading resumed"); return 0


def cmd_daemon(a):
    from .execution import daemon
    daemon.run_forever(_ctx(a), poll_s=a.poll)
    return 0


def cmd_ui(a):
    from .ui.server import serve
    ctx = _ctx(a)
    srv = serve(ctx, port=a.port)
    print(f"control panel: http://127.0.0.1:{srv.server_port}/   mode: {ctx.cfg.broker.kind}")
    print("localhost only. For another machine use an SSH tunnel: ssh -L 8765:127.0.0.1:8765 host")
    if a.with_daemon:
        import threading
        from .execution import daemon
        threading.Thread(target=daemon.run_forever, args=(ctx, a.poll), daemon=True).start()
        print("scheduler running in the background of this process")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tfm_edge", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *args, **kw):
        p = sub.add_parser(name)
        p.add_argument("--config", default="config/bot_paper.yaml")
        for a_, k_ in args:
            p.add_argument(*a_, **k_)
        p.set_defaults(fn=fn)
        return p
    add("preflight", cmd_preflight)
    add("plan", cmd_plan, (["--force"], dict(action="store_true", help="plan even if data looks stale")))
    add("approve", cmd_approve, (["plan_id"], dict(nargs="?", type=int)))
    add("reject", cmd_reject, (["plan_id"], dict(nargs="?", type=int)))
    add("execute", cmd_execute)
    add("reconcile", cmd_reconcile)
    add("status", cmd_status)
    add("report", cmd_report)
    add("kill", cmd_kill, (["--flatten"], dict(action="store_true")), (["--reason"], dict(default="kill switch pressed in the CLI")))
    add("resume", cmd_resume, (["--confirm"], dict(default="")))
    add("daemon", cmd_daemon, (["--poll"], dict(type=float, default=30.0)))
    add("ui", cmd_ui, (["--port"], dict(type=int, default=8765)), (["--with-daemon"], dict(action="store_true")),
        (["--poll"], dict(type=float, default=30.0)))
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (BrokerError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
