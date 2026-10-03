# Build prompt: TimesFM trading bot

Paste into a fresh session. Everything below is the result of building and
adversarially testing the harness in this repo; the ordering and the hard rules
each exist because getting them wrong produced a specific wrong answer.

---

## Context

`timesfm-edge/` already contains a tested Phase 1 gate (56 tests). Do not rebuild
it. Your job is to run it on real data and, only if it passes, build the bot.

## The one rule that decides everything

Break-even hit rate is `0.5 + 0.627k`, where `k = round-trip cost / per-bar
volatility`. Across retail-accessible instruments `k` spans a factor of forty.
Run `python -m tfm_edge.analysis.feasibility` **before** spending any inference.
If a setup's break-even is above ~0.55, or it needs more years than you have, no
model result will save it. Arithmetic rules setups out in one second.

## The setup

US equity cross-section. It is the only configuration that clears the cost hurdle
*and* has enough history to distinguish the result from luck.

- ~70 liquid US large caps, daily bars, 20 years (`config/xs_equity_1d_timesfm25.yaml`)
- Dollar-neutral: long top quintile, short bottom quintile of predicted residual return
- **Beta-residualise both the model input and the target.** The market factor is the
  least predictable and most volatile component; removing it raised IC 0.070 → 0.101
  while cutting target volatility 364 → 300 bps. On the synthetic panel this single
  step is the difference between STOP and PROCEED.
- Point-in-time index membership (`cross_section.universe_path`). Without it every
  name survived to today and the result is an upper bound, not a finding.

Run crypto too if you like, but the arithmetic already says it cannot conclude:
four years of perpetual history against ~46 needed at a plausible edge.

## Non-negotiables

1. **Forecast log returns, never price levels.** Predicting price gives excellent
   error metrics and zero information.
2. **No look-ahead.** Decide at bar close, execute at the next open, target starts
   after that. Prove the harness would catch a leak, don't assume it.
3. **Charge cost on position change, not per bar.** `|w_t − w_{t−1}| × c/2`. Charging
   a full round trip every bar overstates costs by at least 2x and is the worst
   possible execution of any signal.
4. **Annualise from decision timestamps, not bar frequency.** Weekly decisions on
   daily bars annualised by 252 inflates every Sharpe by √5.
5. **Adjusted prices only.** One unadjusted 2-for-1 split is a fake −50% return that
   dominates every real signal. Refuse such a series rather than trading it.
6. **Select sweep cells on the 2x-cost Sharpe, not the headline.** Ranking on 1x
   systematically picks the highest-turnover, most cost-fragile cell (4.28 → 0.41 at
   2x, versus a smoothed cell holding 1.83).
7. **Score with a Deflated Sharpe Ratio** over every swept cell plus every ledger
   variant. The threshold sweep is the largest multiple-testing surface in the
   project and a hit-rate test cannot see it.
8. **The decision layer is deterministic code.** Pure function, no randomness, no
   model call.

## The gate

Proceed to the bot only if all of: DSR > 0.95; still positive at 2x costs; beats
last-sign and AR(1) baselines on the same construction; positive in more than half
the folds; and enough history to have detected the Sharpe it claims.

**If direction fails but calibration passes, stop and say so.** You have a
volatility model, not a trading signal. That is worth real money for position
sizing, bracket widths and variance-premium timing, and none of it requires a
directional edge. Do not build the bot.

## The bot (only past the gate)

- **Forecaster service** — wraps the model, content-addressed cache keyed on
  (weights version, config, input window), so a given input always yields the same
  forecast and an interrupted run resumes free.
- **Decision function** — pure; takes forecast distribution and current costs,
  returns {long, short, flat} plus size. Trade only when expected return net of
  round-trip cost clears an explicit threshold. Default is flat. Size at fixed
  fraction or quarter-Kelly, never full: with an estimated edge, full Kelly overbets
  and accepts drawdowns no human keeps sitting through.
- **Risk layer** — stop and target set at entry, daily loss limit, exposure cap, kill
  switch. Note in code that for a driftless process P(target before stop) ≈
  SL/(SL+TP), so win rate is set by bracket geometry and carries no edge information.
  Never optimise for it.
- **Execution** — paper adapter first, live behind a config flag defaulting to off.
  Log every forecast, decision, fill and outcome with timestamps.
- **Daily divergence report** — live/paper against what the backtest predicted for
  that same period. Divergence is the most important number in the system.

## How to work

Show results at each step. Never present a backtest result without stating what
would have to be true for it to be spurious. If you think the project should stop,
say so directly rather than continuing because you were asked to.

The honest prior for a zero-shot foundation model on liquid instruments is an IC
near zero. A clean, well-evidenced negative is a successful outcome.
