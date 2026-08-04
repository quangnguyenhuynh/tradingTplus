# Rule Backtest Approval Spec

Status: Proposed for Phase 1 implementation.

Last reviewed against repository code: 2026-08-04.

## Goal

Define the smallest production-ready contract for creating explainable T+
strategy rules, replaying those rules on historical features, and approving a
specific rule version before it can write current/future signals.

The rule is not a single daily filter. A valid T+ signal strategy has two
required steps:

```text
Step 1: Daily setup
  -> select symbols worth watching for the next trading session

Step 2: Intraday confirmation
  -> at an allowed scan slot, confirm the daily setup with closed intraday features
  -> create a signal only when both steps pass
```

Backtests must replay the same two-step flow. A daily-only backtest can be a
research diagnostic, but it cannot approve a rule used for live intraday signal
generation.

## Current Repository Context

- `features` is the main rule input.
- Production feature output is persisted for `1d`, `15m`, and `60m`.
- `1d` features are calculated from `stock_daily`.
- `15m` and `60m` features are aggregated from clean `stock_intraday` 1m
  candles during feature computation.
- `stock_intraday` stores only persisted 1m clean source candles.
- Legacy signal/backtest storage was removed by
  `migrations/20260731_drop_legacy_signal_backtest.sql`.
- Do not recreate `trading_signals` or `backtest_data` as active contracts.

## Lifecycle

| Status | Meaning |
| --- | --- |
| `draft` | Rule code/config exists but is not allowed to create live signals. |
| `backtested` | A backtest run has produced evidence for a specific rule version. |
| `approved` | The owner accepted the evidence; the rule version may create live signals. |
| `retired` | Rule version is kept for audit but cannot create new live signals. |

Approval belongs to a specific `strategy_code + version + config_hash`. Any
change to conditions, thresholds, timeframes, scan slots, execution model, fees,
slippage, feature formulas, or historical data eligibility must create new
evidence before approval.

## Inputs

| Layer | Use |
| --- | --- |
| `features` `1d` | Daily setup filter. |
| `features` `15m` / `60m` | Intraday confirmation at scan slots. |
| `stock_intraday` `1m` | Entry-price estimate after a simulated signal. |
| `stock_daily` | H+1/H+3/H+5 closing-price outcomes and daily price context. |
| Trading calendar/session contract | Map setup dates, scan dates, and holding horizons by trading session, not calendar day. |
| Data-quality eligibility | Exclude symbol/date/timeframe windows that are incomplete, invalid, or unverified. |

## Two-Step Rule Contract

Each strategy module must expose one rule object with:

- stable `strategy_code`;
- integer `version`;
- immutable default config;
- required daily timeframe: `1d`;
- required intraday timeframes by scan slot;
- `daily_setup(features_1d) -> RuleDecision`;
- `intraday_confirm(setup, intraday_features, scan_slot) -> RuleDecision`.

`RuleDecision` must include:

- `passed: bool`;
- `reasons: list[str]`;
- `metrics: dict`;
- `input_feature_keys`, including symbol, timeframe, and feature time used.

The live scanner and historical backtest must call the same evaluator code.
The backtest may not duplicate rule logic in a separate implementation.

## Scan Flow

For each trading session `E`:

1. Use the previous trading session `D` to evaluate daily setup.
2. Store symbols that pass daily setup for session `E`.
3. At configured scan slots on `E`, evaluate intraday confirmation only for
   symbols with an active setup.
4. Use only closed feature rows available at or before the scan slot.
5. If confirmation passes, create one signal event for that rule version,
   symbol, setup date, scan slot, and signal time.

Default scan slots are:

```text
09:30
11:30
13:30
14:30
```

A strategy must explicitly declare which intraday timeframes are required for
each slot. If a required closed feature row is missing, the decision is
`not_evaluable`, not `passed`.

## Backtest Flow

For a draft strategy version:

1. Select a historical date range and symbol universe.
2. Apply data-quality eligibility before evaluating rules.
3. Replay daily setup at the end of each historical session `D`.
4. Replay intraday confirmation on the next trading session `E` at the allowed
   scan slots.
5. Create simulated signal events only when both daily and intraday decisions
   pass.
6. Estimate entry using the first tradable clean 1m candle after the signal's
   decision time. Default entry price is the next 1m candle `open`, unless the
   execution model is explicitly changed and versioned.
7. Label outcomes using `stock_daily.close_price` at the close of H+1, H+3, and
   H+5 trading sessions after the entry session.
8. Apply versioned fee, tax, and slippage assumptions to net returns.
9. Record metrics and evidence for review.

Use `H+N` in code/docs for holding-session outcomes. Do not use calendar days,
and do not confuse this with brokerage settlement notation.

If entry or outcome prices are missing, preserve the missing status and exclude
that record from the relevant metric denominator. Do not fill missing prices
with zero or future data.

## Approval Gate

A rule version can become `approved` only when all are true:

- the exact two-step evaluator was used in backtest;
- data-quality filters and excluded rows are reported;
- sample size is reported by strategy, scan slot, symbol universe, and period;
- H+1/H+3/H+5 gross and net return distributions are reported;
- fees, tax, slippage, entry model, and exit model are versioned;
- win rate, average/median return, downside tail, max adverse excursion or
  drawdown proxy, and missing-data counts are reported;
- the owner records an approval decision with notes.

The framework should not hardcode profit thresholds as universal truth. Store
review criteria with the backtest run or strategy review so the project owner can
change approval standards intentionally.

## Proposed Runtime Folders

```text
src/strategies/
  base.py
  registry.py
  breakout_v1.py
  pullback_v1.py
  README.md
  README.vi.md

src/signals/
  daily_setup.py
  scanner.py
  writer.py
  README.md
  README.vi.md

src/backtest/
  replay.py
  execution.py
  outcome.py
  metrics.py
  approval.py
  README.md
  README.vi.md

tests/strategies/
tests/signals/
tests/backtest/
```

## Minimal Database Contracts

The implementation task should create additive migrations for the final schema.
The expected active contracts are:

| Table | Purpose |
| --- | --- |
| `strategies` | Rule metadata, version, config hash, status, and audit fields. |
| `strategy_setups` | Daily setup events for a future trading session. |
| `signals` | Current/future signal events produced only by approved strategies. |
| `backtest_runs` | Backtest scope, assumptions, data filters, code/config version, and summary status. |
| `backtest_signals` | Simulated historical signals and H+1/H+3/H+5 outcomes. |
| `strategy_reviews` | Owner review/approval decision for one strategy version and backtest evidence. |

Every write path must have an explicit idempotency key. Rerunning the same setup,
scan, or backtest must not create duplicates.

## Out of Scope

- AI ranking or probability calibration.
- NAV sizing and portfolio simulation.
- Alert suppression/cooldown policy.
- Foreign-trading or order-book rules.
- Rewriting or retuning the feature pipeline.
- Running backtests automatically after feature computation.
