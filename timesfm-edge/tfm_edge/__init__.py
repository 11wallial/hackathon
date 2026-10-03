"""tfm_edge: an adversarial harness for testing whether a time-series foundation
model has an exploitable directional edge.

Layout (each directory is a stage; nothing later may import from anything earlier
than the stage it needs):

    data/       fetch, cache and validate bars; synthetic generators with known answers
    features/   point-in-time windows and log-return targets, timestamped by knowability
    model/      forecaster protocol, TimesFM wrapper, statistical baselines, forecast cache
    analysis/   purged walk-forward, metrics, multiple-testing ledger, gate, reports
    decision/   pure decision function (parity-tested against the backtest's book)
    risk/       limits, halts, entry brackets
    execution/  paper and Alpaca brokers, engine, ledger, scheduler, preflight
    ui/         local control panel
"""
__version__ = "0.1.0"
