#!/usr/bin/env bash
# Run the harness on real market data. One command, on a machine with open internet.
#
#   ./run_real_data.sh              # preflight, install, feasibility, self-tests, real run
#   ./run_real_data.sh --skip-install
#
# Roughly 1-3 hours on a 4-core CPU, most of it TimesFM inference. Forecasts are cached by
# content, so an interrupted run resumes for free: just run it again.
set -euo pipefail
cd "$(dirname "$0")"
SKIP_INSTALL=0
[[ "${1:-}" == "--skip-install" ]] && SKIP_INSTALL=1
EQUITY_CFG=config/xs_equity_1d_timesfm25.yaml
CRYPTO_CFG=config/xs_crypto_1d_timesfm25.yaml

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[31mSTOP: %s\033[0m\n' "$*" >&2; exit 1; }

say "0/5  Preflight: can this machine actually reach the data and the weights?"
fail=0
for url in https://stooq.com/q/d/l/?s=aapl.us\&i=d \
           https://fapi.binance.com/fapi/v1/ping \
           https://huggingface.co/api/models/google/timesfm-2.5-200m-pytorch; do
  code=$(curl -sS -m 25 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null) || true
  code=${code:-000}
  if [[ "$code" == "200" ]]; then printf '  ok    %s\n' "$url"
  else printf '  FAIL  %s  (HTTP %s)\n' "$url" "$code"; fail=1; fi
done
if [[ $fail -eq 1 ]]; then
  die "One or more hosts above are unreachable, so this stops here rather than half-running.

  000 means the connection never completed: a proxy, firewall or DNS block, not a bad URL.
  A real HTTP code (403, 451, 404) means you reached the host and it turned you away.

  Common causes, in order:
    - a corporate or sandbox egress policy that only allows an approved list of hosts
    - Binance blocks some countries outright; a different host or region fixes that
    - Stooq rate-limits heavy use; wait a few minutes and retry
  You do not need all three. To run only what you can reach:
    equity only:  ./run_real_data.sh --skip-install && python -m tfm_edge.analysis.panel_run --config $EQUITY_CFG
    no network:   ./run_phase1.sh          (synthetic self-tests and the feasibility survey)"
fi

if [[ $SKIP_INSTALL -eq 0 ]]; then
  say "1/5  Install"
  python -m pip install -q -r requirements.txt
  python -c "import torch, timesfm3" 2>/dev/null || python -m pip install -q 'timesfm[torch]'
fi
python - <<'PY'
import importlib.util as u
missing = [m for m in ("numpy","pandas","scipy","statsmodels","arch","matplotlib","torch") if u.find_spec(m) is None]
assert not missing, f"missing packages: {missing}"
print("  environment ok")
PY

say "2/5  Feasibility: what would each setup need from the model?"
echo "  Read this table BEFORE the results below. If a setup's break-even hit rate is"
echo "  above ~0.55, or it needs more years than you have, no model outcome will save it."
python -m tfm_edge.analysis.feasibility --ic 0.03 --plot reports/feasibility.png

say "3/5  Self-tests: the harness must find nothing in noise and find a planted edge"
python -m pytest -q tests
python -m tfm_edge.analysis.panel_run --config config/xs_synthetic_null.yaml
python -m tfm_edge.analysis.panel_run --config config/xs_synthetic_edge.yaml
echo "  If the null run above said anything other than STOP, do not read step 5. Fix the leak."

say "4/5  Baselines on real bars (no TimesFM, minutes not hours)"
echo "  This is the number TimesFM has to beat. If last_sign wins, TimesFM found nothing new."
for f in ar1 last_sign; do
  python -m tfm_edge.analysis.panel_run --config "$EQUITY_CFG" --forecaster $f
  python -m tfm_edge.analysis.panel_run --config "$CRYPTO_CFG" --forecaster $f
done

say "5/5  TimesFM on real bars (the long one)"
echo "  Equity first: it is the only setup with enough history to prove anything."
python -m tfm_edge.analysis.panel_run --config "$EQUITY_CFG"
python -m tfm_edge.analysis.panel_run --config "$CRYPTO_CFG"

say "Done. Reports in reports/"
cat <<'NOTE'
  Read each report in this order:
    1. the verdict line
    2. the survivorship line  (a static universe means the result is an upper bound)
    3. the per-fold Sharpes    (all the profit in one fold is a regime, not an edge)
    4. the baseline rows       (if last_sign wins, TimesFM added nothing)

  PROCEED_UNDERPOWERED means the result may well be real but this much data cannot
  prove it. That is an honest outcome, not a failure to tune. Expect it on crypto:
  four years is not enough at any plausible edge, which the feasibility table in step 2
  said before any of this ran.
NOTE
