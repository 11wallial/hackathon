"""Phase 2 (gated). Intentionally empty.

The decision layer is not built until Phase 1's gate passes. See README.md,
section "Gate criteria". When it is built it must be a pure function:
    decide(forecast: ForecastDist, costs: CostModel, threshold: float) -> (side, size)
with no randomness and no model call.
"""
