"""tfm_edge: an adversarial harness for testing whether a time-series foundation
model has an exploitable directional edge.

Layout (each directory is a stage; nothing later may import from anything earlier
than the stage it needs):

    data/       fetch, cache and validate bars; synthetic generators with known answers
    features/   point-in-time windows and log-return targets, timestamped by knowability
    model/      forecaster protocol, TimesFM wrapper, statistical baselines, forecast cache
    analysis/   purged walk-forward, metrics, multiple-testing ledger, gate, reports
    decision/   (Phase 2, gated) pure decision function
    risk/       (Phase 2, gated) brackets, limits, kill switch
    execution/  (Phase 2, gated) paper and live adapters, ledger
"""
__version__ = "0.1.0"
