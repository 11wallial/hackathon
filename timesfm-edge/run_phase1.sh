#!/usr/bin/env bash
# Reproduces everything end to end.
#   ./run_phase1.sh                 # tests, feasibility, self-tests, setup comparison
#   ./run_phase1.sh config/x.yaml   # one single-instrument config
#   ./run_phase1.sh --xs config/x.yaml   # one cross-sectional config
#
# READ THE FEASIBILITY TABLE FIRST. If a setup's break-even hit rate is above roughly
# 0.55 it will not pass whatever the model does, and running inference on it wastes
# hours to learn something arithmetic already told you.
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "--xs" ]]; then
  shift
  for c in "$@"; do python -m tfm_edge.analysis.panel_run --config "$c"; done
  exit 0
fi
if [[ $# -gt 0 ]]; then
  for c in "$@"; do python -m tfm_edge.analysis.phase1 --config "$c"; done
  exit 0
fi

echo "=== tests"
python -m pytest -q tests

echo; echo "=== which setups can pay for themselves at all"
python -m tfm_edge.analysis.feasibility --ic 0.03 --plot reports/feasibility.png

echo; echo "=== harness self-tests: must find nothing on a martingale, and find the planted edge"
python -m tfm_edge.analysis.phase1 --config config/synthetic_random_walk.yaml
python -m tfm_edge.analysis.phase1 --config config/synthetic_ar1.yaml
python -m tfm_edge.analysis.panel_run --config config/xs_synthetic_null.yaml
python -m tfm_edge.analysis.panel_run --config config/xs_synthetic_edge.yaml

echo; echo "=== same edge, different setups"
python -m tfm_edge.analysis.compare_setups
