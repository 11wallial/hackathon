#!/usr/bin/env bash
# Reproduces Phase 1 end to end.
#   ./run_phase1.sh                       # self-tests on synthetic data, then the real config
#   ./run_phase1.sh config/my.yaml        # a specific config
# The self-tests must show STOP on the random walk and a >0.5 lower bound on the AR(1)
# series before any real-data number is worth reading.
set -euo pipefail
cd "$(dirname "$0")"
python -m pytest -q tests
if [[ $# -gt 0 ]]; then
  for c in "$@"; do python -m tfm_edge.analysis.phase1 --config "$c"; done
else
  python -m tfm_edge.analysis.phase1 --config config/synthetic_random_walk.yaml
  python -m tfm_edge.analysis.phase1 --config config/synthetic_ar1.yaml
  python -m tfm_edge.analysis.phase1 --config config/btc_1h_timesfm25.yaml
fi
