# Runbook: from simulated money to real money

Read the first section even if you read nothing else.

## What this is, and what it is not

This is a **trading machine with its safety systems built in**. It is not evidence that the
strategy makes money.

The Phase 1 gate has never been run on real market data, because the machine that built this
had no internet. So there is **no measured edge**. The honest prior for a zero-shot foundation
model on liquid large caps is an information coefficient near zero, which loses roughly the
trading costs. **Trade only money you expect to lose.** The first real result is going to come
from your own paper run, not from anything written here.

The bot enforces this where it can: live mode refuses to start unless there is a passing
real-data Phase 1 report AND at least 5 paper sessions, or you name each override in the config
and it is logged on every run. Those overrides exist because the decision is yours. They are not
there to be routine.

## The four stages

| stage | broker | money | what you are finding out |
|---|---|---|---|
| 0 | none | none | does TimesFM have an edge at all? (`./run_real_data.sh`) |
| 1 | `paper` (local simulator) | none | does the machinery run unattended for a week? |
| 2 | `alpaca_paper` | fake, on Alpaca | does the real broker API behave as assumed? |
| 3 | `alpaca_live` | real | what does trading actually cost you versus the backtest? |

Do not skip 2. It is the only stage that exercises the Alpaca adapter against the real service,
and that adapter has never touched it.

### Stage 0: measure the edge (needs internet)

```bash
./run_real_data.sh
```
Allow `stooq.com`, `huggingface.co`, `cas-bridge.xethub.hf.co` (see `ALLOWLIST.md`). When it
finishes, `reports/xs_xs_equity_1d_timesfm25.md` has the verdict. The bot reads that file:
a `STOP` verdict is a measured "no", and live mode will show it as a failed `gate` check.

### Stage 1: paper

```bash
./run_bot.sh                       # preflight, then UI at http://127.0.0.1:8765 plus the scheduler
```
Leave it running. Each session it will reconcile at 09:40 and 16:15 ET, plan after 16:20, and
execute at 09:00 the next morning. After five sessions the paper ledger is what unlocks stage 3.

### Stage 2: Alpaca paper

1. Create a paper account at alpaca.markets, generate its API keys.
2. `export APCA_API_KEY_ID=... APCA_API_SECRET_KEY=...`
3. `./run_bot.sh config/bot_alpaca_paper.yaml` (this config requires you to approve each plan).
4. For the first three plans, read every order against Alpaca's dashboard. **Verify these, which
   were built from documentation and never confirmed against the real service:**
   - market-on-open (`opg`) orders are accepted when submitted at 09:00 ET and fill at the open.
     If Alpaca rejects them, set `broker.order_tif: day`; the fill then lands at the first print.
   - short sales are accepted and `shorting_enabled` is true on the account.
   - the OCO exit bracket (stop + target) appears as one order per position after the 09:40 reconcile.
   - order status strings, partial fills and `filled_avg_price` come back as the adapter expects.
   - positions report a negative quantity for shorts.

### Stage 3: live

```bash
cp config/bot_live.example.yaml config/bot_live.yaml      # read every line, set capital and max_capital
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...        # the LIVE account's keys
export TFM_LIVE=YES_TRADE_REAL_MONEY
python -m tfm_edge preflight --config config/bot_live.yaml
```
Preflight must say **GO**. A NO-GO names what failed and which config line overrides it, if one does.
Then `./run_bot.sh config/bot_live.yaml`. The page shows an amber `LIVE · REAL MONEY` badge throughout.

**Capital.** Below about $15,000, whole-share rounding distorts a 28-name book (each slot is under
$550, and a $300 stock rounds to 1 or 2 shares). The plan warns you when rounding exceeds 10% of
intended exposure. Use a dedicated account: positions outside the bot's universe are left alone, but
a shared account makes every P&L number ambiguous.

**First live week.** Approve every plan by hand, after reading it. Consider `book.gross: 0.5`.
Expect the first fills to differ from the ideal book; the daily divergence report says by how much.

## The daily rhythm (automatic with `--with-daemon`)

```
09:00  execute approved plan   -> orders go in, queued for the open
09:40  reconcile               -> fills recorded, equity snapshotted, stop+target placed on new positions
16:15  reconcile               -> end-of-day equity, limits checked
16:20+ plan                    -> forecast, decide, size, risk-check; waits for your approval
```
A plan not executed by 09:25 ET is **expired, never run late**. Yesterday's decision at today's
10:00 price is a different trade from the one that was backtested.

## Stopping it

| how | effect |
|---|---|
| UI **KILL** / `python -m tfm_edge kill` | halts; cancels working entry orders; **leaves protective stops** |
| UI **KILL + FLATTEN** / `kill --flatten` | also closes every position at market |
| `touch state/KILL` | halts every mode at once, from any shell, even if the UI or database is wedged |
| daily loss limit, drawdown limit | automatic halt (and optionally flatten: `risk.flatten_on_halt`) |

Resuming needs the typed word `RESUME`, and refuses while `state/KILL` exists: that file is the one
switch this program will never clear for you. Stops stay in place during a halt because a stop only
ever reduces a position; cancelling them would make a halt riskier.

## What stops the bot from trading

Stale bars, thin data coverage (under 90% of the universe), a data source that is down, a plan that
fails any risk limit, positions that changed between plan and execute, a blocked broker account,
a plan older than 09:25, and the kill switch. Each writes a blocked plan with the reason, visible in
the UI. A blocked plan places no orders.

## Reading the divergence report

`reports/live/<name>-<date>.md`, also in the UI. It compares **account** to **ideal book** (the
exact weights the decision function chose, held perfectly, with the modelled costs), and against the
Phase 1 backtest's expected return per day.

- **Gap** (account minus ideal): what trading costs you versus the backtest's assumptions. Large or
  drifting means the cost model is wrong, whatever the signal does. Watch this first.
- **z vs backtest**: after a handful of days it is wide. A few days cannot confirm an edge; they can
  only contradict one.

## What has NOT been verified

Be as sceptical of this list as of the strategy.

- **The Alpaca adapter has never spoken to Alpaca.** Tested against a stand-in server that implements
  the documented shapes; that proves internal consistency, not that Alpaca behaves like the stand-in.
- **TimesFM weights have never been loaded here.** The wrapper is tested against a random-weight model
  object. `preflight` loads the real model and runs a forecast; do not skip it.
- **Stooq data has never been fetched here.** Both loaders are tested against stand-in servers.
- **The holiday calendar is weekdays only.** Holidays are caught by the stale-data check and by the
  broker rejecting orders, not by the calendar.
- **Stops are daily-sigma disaster stops, not part of the validated edge.** The backtest held without
  stops, so a stop that fires is live behaviour it never modelled. The target caps winners too.
- **Not modelled:** dividends, short borrow fees and financing. They appear as divergence. Hard-to-borrow
  shorts can cost a lot; the bot skips names that are not easy to borrow.
- **Pattern-day-trader rule.** Under $25k, a stop that fires on the day a position was opened is a day trade.
- **A stock split on a held name** changes the share count at the broker; the bot reads positions fresh
  each plan, but watch the first plan after one.
- **Plans use the last close for sizing; fills happen at the open.** Overnight gaps shift the realised
  weights from the planned ones. The divergence report absorbs this.
