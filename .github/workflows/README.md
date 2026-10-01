# GitHub Actions workflows

Automation for tests and explicit Trading T+ pipelines.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Current workflows

| File | Trigger | Current command |
| --- | --- | --- |
| `tests.yml` | Pull requests and pushes to `dev` | `python -m pytest -q` on Python 3.11, with a PostgreSQL 16 service and `TEST_DATABASE_URL`. |
| `stock-eod.yml` | Weekdays 09:30 UTC (16:30 Vietnam) + manual | Daily-only `python main.py stock-eod [date]`. |
| `stock-intraday.yml` | Weekdays 10:00 UTC (17:00 Vietnam) + manual | 1m-only `python main.py stock-intraday [date]`. |
| `index-eod.yml` | Tuesday-Saturday 01:00 UTC (08:00 Vietnam) + manual | Scheduled runs call `python main.py index-daily <previous-calendar-day> [--indexes ...]`; manual runs use the supplied date when present. |
| `features.yml` | Manual dispatch only | Explicit `python main.py features ...`. |

## Operational notes

- `stock-eod.yml` runs daily ingest and daily-only completeness for `symbols.status = 'active'`.
- `stock-intraday.yml` runs 1m ingest and intraday-only completeness for rows where both `status` and `intraday_status` are `active`. Manual symbols cannot bypass this automatic scope.
- Both workflows are independent from index and never compute features/signals/backtests/Analog.
- `index-eod.yml` runs only SSI DailyIndex raw/clean ingest through `index-daily`. Scheduled runs execute at 08:00 Vietnam time on Tuesday-Saturday and explicitly ingest the previous calendar day so next-morning SSI proprietary-trading totals can be captured. Manual dispatch keeps the existing explicit date behavior; if no manual date is supplied, the workflow also targets the previous calendar day. An empty index input uses active `index_master` rows; explicit indexes can retry or catch up source rows without running stock ingest, completeness, features, signals, backtests, or Analogs.
- The scheduled workflow intentionally uses the previous calendar day. It does not infer an exchange holiday calendar; empty SSI responses remain visible in the command summary and no fake data is created.
- `features.yml` is intentionally separate from ingest and supports explicit mode/date/symbol/timeframe inputs.
- SSI/Supabase credentials are provided through repository secrets.
- The atomic-replace PostgreSQL test is part of the main suite and must execute,
  not skip, because `tests.yml` always supplies its test database.
- Long-history parity and all pagination regression modules are collected by the
  same unfiltered `python -m pytest -q` command on pull requests and `dev` pushes.
- Do not add automatic signal or backtest execution to ingest workflows without an explicit architecture task.

## Validation

Review workflow YAML, run the corresponding local command, and rely on `tests.yml` for offline test coverage before merging.
