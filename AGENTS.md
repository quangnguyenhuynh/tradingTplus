# AGENTS.md

## Project

Trading T+ is a Python application for collecting, validating,
processing and backtesting Vietnamese stock market data.

## Current development phase

Phase 0: data infrastructure and data validation.

The priority order is:

1. Correct raw data
2. Correct clean data
3. Data completeness checks
4. Reproducible feature computation
5. Signals
6. Backtesting
7. Strategy optimization

Do not skip earlier stages.

## Architecture constraints

- Keep daily and intraday pipelines separate.
- Keep raw and clean tables separate.
- Feature computation must be a separate explicit pipeline.
- Do not automatically compute features after daily or intraday ingestion.
- All feature jobs must support rerun and backfill.
- Database schema changes require a migration.
- Do not silently rename tables, columns or public functions.
- Preserve backward compatibility unless the task explicitly removes it.

## Coding rules

- Read existing implementation before editing.
- Prefer small, isolated changes.
- Do not refactor unrelated code.
- Reuse existing repository patterns.
- Add type hints where practical.
- Handle API and database errors explicitly.
- Do not hide exceptions without logging them.

## Data rules

- Never fabricate trading data.
- Non-trading days must not create fake daily records.
- Validate duplicate keys before inserts.
- Intraday completeness must be checked per symbol and trading date.
- Clearly distinguish cumulative volume from candle volume.
- Monetary value units must be documented and consistent.

## Before implementation

Provide:

1. Current behavior
2. Root cause
3. Proposed changes
4. Files affected
5. Database impact
6. Test plan

## Completion criteria

A task is not complete until:

- relevant tests pass;
- smoke-check commands are supplied;
- changed files are listed;
- database migrations are included when required;
- known risks are reported.