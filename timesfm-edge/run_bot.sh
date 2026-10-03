#!/usr/bin/env bash
# Preflight, then start the control panel and the scheduler together.
#   ./run_bot.sh                              # paper (simulated broker)
#   ./run_bot.sh config/bot_alpaca_paper.yaml
#   ./run_bot.sh config/bot_live.yaml         # real money: needs TFM_LIVE=YES_TRADE_REAL_MONEY
# If preflight says NO-GO it does not start. Fix every [FAIL] first.
set -euo pipefail
cd "$(dirname "$0")"
CFG="${1:-config/bot_paper.yaml}"
python -m tfm_edge preflight --config "$CFG" || { echo; echo "preflight NO-GO: not starting."; exit 1; }
echo
exec python -m tfm_edge ui --config "$CFG" --with-daemon
