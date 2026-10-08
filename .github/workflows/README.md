# GitHub Actions workflows

Automation for tests and explicit Trading T+ pipelines.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Current workflows

| File | Trigger | Current command |
| --- | --- | --- |
| `tests.yml` | Pull requests and pushes to `dev` | `python -m pytest -q` on Python 3.11, with a PostgreSQL 16 service and `TEST_DATABASE_URL`. |
| `stock-eod.yml` | Weekdays 09:30 UTC (16:30 Vietnam) + manual | Resolves a Vietnam-local schedule date, then runs daily-only `python main.py stock-eod <date>`. |
| `stock-intraday.yml` | Weekdays 10:00 UTC (17:00 Vietnam) + manual | 1m-only `python main.py stock-intraday <date>`. |
| `index-eod.yml` | Tuesday-Saturday 01:30 UTC (08:30 Vietnam) + manual | Scheduled runs call `python main.py index-daily <previous-intended-Vietnam-calendar-day> [--indexes ...]`; manual runs use the supplied date when present. |
| `features.yml` | Manual dispatch only | Explicit `python main.py features ...`. |

All three ingest workflows declare UTC cron without `timezone`. Their UTC cron expressions are `30 9 * * 1-5` (Stock EOD), `0 10 * * 1-5` (Stock Intraday), and `30 1 * * 2-6` (Index EOD). Explicit timezone does not guarantee punctual execution; keep centralized scheduled-slot date resolution.

## Operational notes

- `stock-eod.yml` runs daily ingest and daily-only completeness for `symbols.status = 'active'`. A scheduled run resolves the latest Monday-Friday 16:30 Vietnam schedule slot and explicitly passes that slot's date, so a delayed runner that starts after Vietnam midnight does not roll into the next date. A manual date is preserved; a manual run without one uses the existing latest-weekday-on-or-before-today Vietnam fallback.
- `stock-intraday.yml` runs 1m ingest and intraday-only completeness for rows where both `status` and `intraday_status` are `active`. Manual symbols cannot bypass this automatic scope. Scheduled runs resolve the latest Monday-Friday 17:00 Vietnam slot and pass its date explicitly, including when the runner starts after midnight. Explicit manual dates win; no-input manual runs keep the CLI calendar fallback.
- Both workflows are independent from index and never compute features/signals/backtests/Analog.
- `index-eod.yml` runs only SSI DailyIndex raw/clean ingest through `index-daily`. Scheduled runs execute at 08:30 Vietnam time on Tuesday-Saturday, resolve the latest intended schedule slot, and explicitly ingest the calendar day before that slot so next-morning SSI proprietary-trading totals can be captured. Manual dispatch keeps an explicit supplied date; if no manual date is supplied, it preserves the existing previous-runtime-calendar-day behavior. An empty index input uses active `index_master` rows; explicit indexes can retry or catch up source rows without running stock ingest, completeness, features, signals, backtests, or Analogs.
- GitHub Actions cron jobs may start later than their configured slot. All three workflows log the event, actual Vietnam runtime, scheduled Vietnam slot, resolved target date, and whether the target came from scheduled, manual, or default resolution; they do not use the delayed runner's calendar date naively for scheduled targets.
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

Scheduled targets use the latest elapsed `Asia/Ho_Chi_Minh` cron slot: Stock EOD 16:30 and Stock Intraday 17:00 target that session date; Index EOD 08:30 the next morning targets the previous calendar day. This handles overnight stock delays and same-morning index delays. If execution is delayed past another scheduled slot, the original trigger date cannot be recovered from runtime alone; use an explicit manual date for catch-up.
