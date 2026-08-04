# Codex Task: Implement Rule Backtest Approval Framework

Repository: `quangnguyenhuynh/tradingTplus`

Base branch: `dev`

## Objective

Implement the Phase 1 framework for designing strategy rules, replaying the same
two-step rule flow in backtests, and approving a specific rule version before it
can write current/future signals.

The intended lifecycle is:

```text
draft rule
  -> backtest daily setup + intraday confirmation on historical features
  -> record H+1/H+3/H+5 evidence
  -> owner approves one strategy version
  -> only approved versions may create live signals
```

## Read First

Read these files before coding:

- `AGENTS.md`
- `docs/phase1/RULE_BACKTEST_APPROVAL_SPEC.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/CURRENT_STATE.md`
- `src/features/README.md`
- `src/features/common.py`
- `src/features/daily.py`
- `src/features/intraday.py`
- `src/features/runtime.py`
- `src/database/client.py`
- `migrations/20260731_drop_legacy_signal_backtest.sql`
- related tests under `tests/features/`, `tests/cli/`, and `tests/validation/`

Then report the 10 required pre-code items from `AGENTS.md`.

## Scope

Implement new code only. Do not restore legacy signal/backtest behavior.

Create:

```text
src/strategies/
src/signals/
src/backtest/
tests/strategies/
tests/signals/
tests/backtest/
```

Each new `src` and `tests` package/folder must include `README.md` and
`README.vi.md`.

## Core Requirements

### Strategy framework

- Add a shared strategy interface in `src/strategies/base.py`.
- Add a registry in `src/strategies/registry.py`.
- Implement at least two draft example strategies:
  - `BREAKOUT_V1`
  - `PULLBACK_V1`
- Each strategy must expose:
  - stable `strategy_code`;
  - integer `version`;
  - immutable config;
  - `daily_setup(...)`;
  - `intraday_confirm(...)`;
  - required intraday timeframes per scan slot.
- The rule evaluator must return a structured decision with:
  - `passed`;
  - `status` such as `passed`, `failed`, `not_evaluable`;
  - `reasons`;
  - `metrics`;
  - feature keys used.

### Signal framework

- Implement `src/signals/daily_setup.py` to create setup candidates from
  `features` timeframe `1d`.
- Implement `src/signals/scanner.py` to confirm candidates at scan slots using
  closed `15m`/`60m` feature rows.
- Implement `src/signals/writer.py` with idempotent writes.
- Live/current signal scans must reject strategy versions that are not
  `approved`.
- Daily setup is not a signal. A signal exists only after intraday confirmation.

### Backtest framework

- Implement `src/backtest/replay.py` to replay the same strategy evaluator over
  historical dates:
  - daily setup on session `D`;
  - intraday confirmation on next trading session `E`;
  - simulated signal only if both steps pass.
- Implement `src/backtest/execution.py`:
  - entry estimate uses the first tradable clean `stock_intraday` 1m candle after
    signal decision time;
  - default entry price is that candle's `open`;
  - missing entry must be explicit.
- Implement `src/backtest/outcome.py`:
  - outcomes use `stock_daily.close_price` at H+1, H+3, and H+5 trading-session
    closes after the entry session;
  - missing outcomes must be explicit.
- Implement `src/backtest/metrics.py` for sample size, gross/net return,
  win-rate, average/median return, downside tail, and missing counts.
- Implement `src/backtest/approval.py` so a strategy version can be moved to
  `approved` only with stored backtest evidence and an explicit review decision.

### Database

Create one additive migration using the existing date-prefixed naming style.
Do not modify raw, clean, or `features` tables.

Expected active tables:

- `strategies`
- `strategy_setups`
- `signals`
- `backtest_runs`
- `backtest_signals`
- `strategy_reviews`

Every write path needs a unique/idempotency key. Include verification SQL and
rollback guidance in the migration. Do not recreate `trading_signals` or
`backtest_data`.

### CLI

Add explicit commands without changing existing CLI behavior:

- `python main.py strategies list`
- `python main.py strategies backtest ...`
- `python main.py strategies approve ...`
- `python main.py signals daily-setup ...`
- `python main.py signals scan ...`

Signal/backtest commands must never run from ingest, EOD, or feature commands.

## Constraints

- Use `features` as the primary rule input.
- Use `stock_intraday` only for execution/entry estimation.
- Use `stock_daily` for holding-session outcomes.
- Use trading sessions, not calendar days, for H+1/H+3/H+5.
- Do not use future feature rows.
- Use only closed intraday feature rows available at the scan slot.
- Do not add AI, probability, NAV, alert cooldown, foreign trading, or orderbook
  logic in this task.
- Do not tune rule thresholds for profitability in this task. Keep example rules
  transparent and testable.
- Do not write production data in tests.

## Acceptance Criteria

- Draft strategies can be registered and evaluated offline.
- Backtest uses the same two-step evaluator used by signal scan.
- Daily-only results cannot approve a live intraday signal strategy.
- Unapproved strategies cannot write live signals.
- Rerunning daily setup, signal scan, and a backtest is idempotent.
- H+1/H+3/H+5 outcomes are based on trading sessions and close prices.
- Missing entry/outcome data is preserved, not filled.
- Migration is additive and includes verification SQL.
- README.md and README.vi.md exist for new source and test folders.

## Tests

Add unit tests for:

- strategy registry;
- daily setup pass/fail/not-evaluable;
- intraday confirmation pass/fail/not-evaluable;
- no signal from unapproved strategy;
- no duplicate setup/signal on rerun;
- backtest replay uses both daily and intraday steps;
- H+1/H+3/H+5 outcome session mapping;
- missing entry and missing outcome behavior;
- migration text contains required tables, unique keys, verification SQL, and no
  legacy table recreation.

Run:

```bash
python -m pytest -q tests/strategies tests/signals tests/backtest
python -m pytest -q tests/features tests/cli
python -m compileall main.py src scripts tests
python main.py --help
```

If credentials are missing, do not run live SSI/Supabase smoke tests. Report them
as not run.

## Final Report Required

Report:

- what changed;
- files changed;
- migration/database impact;
- whether backfill is required;
- test commands run;
- test results;
- remaining risks;
- next step.
