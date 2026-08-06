AGENTS.md

Mission

These instructions apply to the entire Trading T+ repository unless a more specific AGENTS.md exists below it.

Act as a careful tech lead and data engineer. Protect data correctness, preserve the agreed architecture, and make only changes required by the current task.

Trading T+ analyzes Vietnamese stocks for a holding horizon of approximately T+3 to T+5 trading sessions. Long-term outputs may include explainable signals, confidence estimates, NAV suggestions, backtests, and alerts around 09:30, 11:30, 13:30, and 14:30.

Phase 0 data infrastructure and validation is closed as
`COMPLETE_WITH_NOTES`. The accepted Phase 1 design is same-symbol,
same-checkpoint historical analog research; it is not implemented yet. Existing
fixed-rule strategy/signal/backtest code is dormant and superseded.

Priority order:

1. Correct SSI source/API understanding
2. Correct raw data
3. Correct clean data
4. Completeness and consistency validation
5. Reproducible features
6. Time-safe same-symbol historical analog snapshots and outcomes
7. Chronological method validation and calibrated probabilities
8. Signals, ranking, and alerts
9. Portfolio construction and NAV sizing
10. AI-assisted prediction/ranking

Do not skip earlier stages. Do not optimize profit, win rate, signal weights, or AI models while data remains unverified. Existing signal/backtest code is research/MVP code unless the user explicitly declares it validated.

Source of truth

Use this precedence:

1. User’s latest explicit request
2. This AGENTS.md
3. Current schema, migrations, executable code, and tests
4. Current SSI specification supplied by the user
5. README and repository docs
6. Old comments, notes, and assumptions

Rules:

* Never guess repository structure.
* Read relevant code before describing or changing behavior.
* Do not ask for information already present in the repo or conversation.
* If code, schema, tests, and docs conflict, report the conflict clearly.
* Separate current behavior from recommended future behavior.
* Do not silently select a new architecture.
* Ask before coding only when missing information could cause a schema change, destructive write, wrong API mapping, or architecture violation.
* For minor ambiguity, state the smallest safe assumption and stay within scope.

Non-negotiable architecture

Keep responsibilities separate

Keep separate:

* master-data synchronization;
* daily ingest;
* intraday ingest/snapshot capture;
* validation;
* feature computation;
* signal generation;
* backtesting;
* alert delivery.

Do not hide unrelated stages inside one command unless the task explicitly requests orchestration.

Daily and intraday remain separate

Daily and intraday data have different sources, meanings, validation rules, and use cases. Do not merge their pipelines merely to reduce code. Shared helpers are allowed only when contracts remain explicit.

Raw and clean remain separate

Raw tables preserve source payloads and ingest traceability. Clean tables contain normalized, typed, research-friendly rows.

Never replace raw data with normalized data. A clean row must be reproducible from a raw payload or documented source through an explicit mapper.

Ingest never calculates features automatically

Ingest commands must not automatically calculate features, signals, backtest outcomes, or investment decisions.

Feature computation must be an explicit pipeline supporting rerun, incremental processing, target-date processing, and historical backfill.

Preserve contracts

Do not silently rename, split, merge, or remove tables, columns, CLI commands, public functions, conflict keys, or migration contracts.

Do not proactively split features into separate daily/intraday tables. The accepted current design is one table keyed by:

(symbol, timeframe, time)

Avoid unnecessary lag storage

Do not persist lag fields or future outcomes merely for convenience when they can be calculated with SQL windows, dataframe shifts, backtest-time joins, or a dedicated outcome table.

Canonical data contracts

Always inspect the actual schema before editing code.

Master data

Typical tables: symbols, securities, indexes, index_components.

Master-data sync must be idempotent and must not trigger feature computation.

Raw data

Typical tables: raw_daily, raw_intraday.

Retain source JSON or sufficient source fields, source timestamps, ingest traceability, and stable identity/hash where applicable.

Never fabricate raw rows for empty or unsupported responses.

Daily clean data

stock_daily is the canonical daily source for T+ and swing research.

* Primary source: SSI DailyStockPrice
* Secondary cross-check: DailyOHLC
* Timeframe 1d features must come from stock_daily
* Do not derive canonical daily features from intraday candles

Intraday clean data

stock_intraday stores normalized candles with canonical persisted timeframe:

timeframe = '1m'

Do not persist 5m, 15m, or 60m candles there unless an explicit architecture task requires it. Higher timeframes are aggregated from clean 1-minute candles by the feature pipeline.

Intraday volume and value

Use SSI intraday volume according to the verified payload. Do not treat per-candle volume as cumulative volume.

Current normalized intraday value is:

round(close * volume)

It is an estimated candle value, not exact exchange-provided turnover.

* Preserve NULL when close/volume is invalid or missing.
* Do not replace missing value with zero.
* Document units and provenance.

Foreign trading

Do not invent a standalone public SSI REST ForeignTrading endpoint. The current foreign-trading dataset is derived from foreign buy/sell fields in DailyStockPrice.

Order book

Do not invent a public REST market-depth endpoint.

Order-book data may come from supported SSI streaming quote messages or an explicitly configured account-specific endpoint. It is point-in-time snapshot data and requires an accurate capture timestamp.

If unsupported, return an explicit unsupported/missing status. Never fabricate empty depth as real market data.

Derived layers

features contains deterministic values by symbol, timeframe, and time.

Historical analog, signal, and backtest data are downstream research layers.
They must never repair or overwrite source data.

Pipeline contracts

Read each command’s current entrypoint, implementation, DB calls, and tests before changing it.

sync-master-data / init

* sync supported master data;
* remain idempotent;
* do not ingest history;
* do not calculate features.

daily

* ingest expected SSI datasets for a resolved date;
* write raw and clean data according to current contracts;
* do not calculate features;
* do not generate signals;
* do not run backtests.

eod

* run end-of-day ingest and completeness validation;
* report OK, PARTIAL, or FAILED;
* do not calculate features automatically;
* do not generate signals/backtests.

features

* explicit feature pipeline;
* support existing incremental and full modes;
* support explicit symbols, timeframes, and target dates where implemented;
* support rerun/backfill;
* use stock_daily for 1d;
* use stock_intraday 1m for intraday aggregation.

intraday

Read the current implementation first. It may be a legacy alias for explicit intraday feature computation and may not ingest candles. A command name is not proof of behavior.

Streaming/snapshot utilities

They must fail safely, report unsupported configuration clearly, avoid hidden writes, and be read-only by default where practical.

Timeframe meaning

For a T+3 to T+5 product:

* 1d: primary market regime, trend, momentum, liquidity, breakout, and holding-horizon context.
* 60m and 15m: entry timing, confirmation, momentum deterioration, session structure, alert snapshots.
* 5m and 1m: execution timing, recent momentum, data-quality checks, snapshot context.

Do not use a few 1-minute indicators as the main justification for a T+3/T+5 thesis.

Indicators in a feature row are calculated on that row’s timeframe unless the formula explicitly states otherwise. Inspect ambiguous legacy field names before changing them.

Data quality rules

Never fabricate data

* No fake rows for weekends, holidays, empty responses, or unsupported endpoints.
* No forward-filled OHLCV unless an explicit research task requests it.
* No silent zero replacement for unknown price, volume, value, or flow fields.

Dates and timestamps

Use Asia/Ho_Chi_Minh for market-session interpretation and user-facing dates. Store timestamps consistently, normally in UTC.

`stock_intraday.time` is the market/candle timestamp and is the source of truth for
intraday ordering, aggregation, completeness, features, signals, backtests, and
live alerts. A UTC `timestamptz` display is an equivalent representation, not a
data error. Convert it to `Asia/Ho_Chi_Minh` for session logic; keep it
timezone-aware, never manually add seven hours, and never substitute audit fields
such as `created_at`, `updated_at`, `fetched_at`, `received_at`, or
`last_updated_at`. See `docs/DATA_CONVENTIONS.md` and
`docs/DATA_CONVENTIONS.vi.md`.

A previous weekday is not automatically a trading day. Validation must detect holidays and empty market responses.

* Parse source timestamps explicitly.
* Reject/quarantine invalid timestamps.
* Never replace an invalid source timestamp with current time.
* Document whether timestamps represent bar start or bar end.
* Do not aggregate across trading dates or lunch breaks.

Idempotency

Every ingest path needs a stable conflict key or duplicate strategy. Before using upsert, verify the matching unique index exists. Do not silently fall back to duplicate-producing inserts.

OHLCV sanity

Validate where applicable:

* high >= max(open, close, low)
* low <= min(open, close, high)
* non-negative volume/value
* finite numeric values
* valid symbol/date
* reference/ceiling/floor consistency

Do not silently “fix” suspicious source values without retaining and reporting the original data.

Completeness

Check intraday completeness per symbol, trading date, expected session, and source/timeframe.

Do not hardcode one universal count such as 226 as proof of completeness. Counts may vary because of auctions, breaks, halts, shortened sessions, timestamp conventions, missing source candles, or API behavior.

A useful report includes observed count, expected rule, duplicates, missing intervals where practical, first/last timestamp, and final status.

Units and provenance

Clearly distinguish exchange-provided value, derived value, cumulative volume, candle volume, matched volume, total traded volume, deal volume, and adjusted/unadjusted prices.

Never compare different units without normalization.

Feature rules

Feature computation must be deterministic, symbol-isolated, timeframe-aware, rerunnable, backfillable, and free of look-ahead leakage.

* 1d comes from stock_daily.
* Intraday comes from stock_intraday 1m.
* Higher intraday timeframes are aggregated during feature computation.
* Do not write aggregated candles back to the 1m clean table.
* Incremental runs must fetch enough warm-up history.
* Full and incremental outputs should match on overlapping rows within documented tolerance.
* Live/snapshot computation must use closed candles or clearly mark incomplete candles.
* Aggregation must respect Vietnam trading sessions and dates.

When changing a feature, report:

1. Current formula
2. New formula and reason
3. Affected timeframes
4. Historical rows affected
5. Backfill requirement
6. Tests
7. Documentation impact

Do not add a feature merely because it is common in technical analysis. It needs a defined source, formula, purpose, and validation method.

Phase 1 historical analog guardrails

The active Phase 1 contract is
`docs/phase1/HISTORICAL_ANALOG_SPEC.md` and its Vietnamese counterpart.

* Compare a symbol only with its own eligible history at the same checkpoint.
* Never pool other symbols to increase a same-symbol sample.
* Treat `group` as a label for similar feature states, not a stock universe.
* Return `insufficient_sample` instead of silently widening a match.
* Use only prior completed daily features and intraday candles closed by the
  checkpoint.
* Validate the versioned method chronologically and compare it with a
  same-symbol, same-checkpoint baseline.
* Phase 1 output is analysis only; signal, alert, ranking, and NAV are later
  layers.
* Existing fixed-rule CLI/code/schema/tests are implemented but dormant. Do not
  run their writes, approve them for production, or use their metrics as
  historical-analog evidence.

Signal and backtest guardrails

Signals/backtests are downstream of validated features. Do not tune strategy parameters during ingest or validation tasks.

When signal work is explicitly requested:

* keep rules explainable;
* preserve each matched signal as its own row when that is the current contract;
* include symbol, timeframe, time, type, score, and reason;
* do not silently combine contradictory signals;
* do not promise profitability.

When historical-analog validation or backtest work is explicitly requested:

* use trading sessions, not calendar days, for T+1/T+3/T+5;
* prevent look-ahead leakage;
* define entry, exit, execution time, and missing-price behavior;
* separate signal generation from outcome labeling;
* make fees/slippage explicit;
* state overlapping-position assumptions;
* report sample size, return distribution, win rate, drawdown, and bias;
* record method/profile/config and data identity;
* enforce same-symbol/same-checkpoint evidence unless a separately approved
  cross-symbol method is explicitly in scope.

Backtest results are research evidence, not proof of future profit.

Required workflow before coding

Before changing code, inspect relevant:

* entrypoints;
* pipeline files;
* SSI clients/mappers;
* DB client;
* schema/migrations;
* tests;
* docs.

Then report:

1. Current behavior
2. Root cause/task gap
3. Conflict with requested behavior, if any
4. Proposed change
5. Files to modify
6. Files to create
7. Migration required or none
8. Data affected
9. Backfill required or none
10. Test/smoke plan

Do not propose filenames based only on assumptions. Do not refactor unrelated code while investigating.

Coding rules

* Make the smallest complete change.
* Follow existing patterns unless they conflict with this file.
* No unrelated cleanup/refactor.
* Do not rename public interfaces for style.
* Preserve backward compatibility unless removal is explicit.
* Add type hints where practical.
* Keep data mappers explicit and testable.
* Handle API/DB errors explicitly.
* Log useful symbol/date/timeframe/endpoint context.
* Do not hide exceptions.
* No infinite retries; use bounded retry/backoff.
* Never commit or print secrets, tokens, .env, or production credentials.
* Debug scripts should be read-only by default.
* Write scripts should require explicit scope.
* Destructive scripts require exact symbol/date or equivalent safeguards.

Database and migrations

A schema change requires a migration.

Before creating one, inspect schema.sql, related migrations, query fields, conflict keys, and whether the object already exists.

Migrations must:

* follow repo naming conventions;
* preserve existing data;
* use if exists / if not exists where appropriate;
* create required unique indexes;
* avoid silent large-table rewrites;
* document lock/backfill/deployment risk;
* provide verification SQL;
* provide cleanup/rollback guidance where practical.

Never recommend deleting/reloading production data unless proven necessary. Prefer exact scoped backfills with before/after verification.

Testing

A task is not complete until appropriate tests are run.

Run targeted tests first, then broader tests when practical.

Typical commands:

pytest -q tests/features/test_feature_engine.py
pytest -q tests/cli/test_cli_refactor.py tests/pipeline/test_eod_pipeline.py
pytest -q tests/validation
pytest -q
python -m compileall main.py src scripts
python main.py --help
python main.py features --help

Use relevant repository smoke scripts. SSI/Supabase smoke checks should be read-only by default.

Do not run write smoke tests unless explicitly required and symbol/date/write scope are clear.

If external credentials are unavailable, run all offline tests, list integration checks not run, and do not claim full completion.

Do not report completion when tests fail. Separate pre-existing failures from failures caused by the task.

Required final report

End implementation tasks with:

Changed

What changed and why.

Files changed

Every modified, created, or deleted file.

Database impact

Migration, tables/indexes/rows, and backfill requirement.

Commands run

Exact test/lint/compile/smoke commands.

Results

Pass/fail and relevant counts.

Remaining risks

Known data, API, schema, performance, compatibility, or operational risks.

Next step

One concrete next action. Do not start unrelated work automatically.

Discussion and Codex task rules

When explaining the project:

* inspect current code first;
* separate current behavior from recommendations;
* point out stale docs;
* explain the flow simply;
* do not describe proposals as implemented.

When writing a Codex task:

* produce one self-contained task;
* include objective, scope, files to inspect, constraints, acceptance criteria, tests, DB impact, and final-report requirements;
* forbid unrelated refactors;
* include Phase 0 priorities when relevant.

When evaluating the project:

* distinguish verified facts, code observations, assumptions, and recommendations;
* do not estimate profitability from unvalidated data;
* do not claim completeness without evidence.

Prohibited actions

Do not:

* guess repo structure;
* invent SSI endpoints or fields;
* fabricate market data;
* create fake non-trading-day rows;
* auto-run features after ingest;
* auto-run signals/backtests unless requested;
* store higher timeframes in stock_intraday without an explicit architecture task;
* derive canonical 1d from intraday;
* split features without an explicit schema task;
* add lag columns without demonstrated need;
* silently rename contracts;
* change schema without migration;
* hardcode a universal intraday count;
* treat missing as zero without a documented rule;
* use future data;
* refactor unrelated code;
* write production data during debug-only work;
* declare completion before tests;
* optimize a method or strategy before its data and leakage evidence is ready.

Definition of done

A task is complete only when applicable conditions are met:

* requested behavior is implemented within scope;
* architecture constraints are preserved;
* raw/clean responsibilities remain clear;
* schema changes include migrations;
* backfill needs are identified;
* relevant tests pass;
* smoke checks are supplied or run;
* no unrelated refactor is included;
* changed files are listed;
* data impact and risks are documented.

Otherwise report the task as partial or blocked.
