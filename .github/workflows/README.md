# GitHub Actions — TradingTPlus

## Active scheduled EOD workflows

| Workflow | Vietnam schedule | UTC cron | Explicit target date |
| --- | --- | --- | --- |
| `stock-eod-scheduled.yml` | 17:07 Monday–Friday | `7 10 * * 1-5` | The same Vietnam calendar day |
| `index-eod-scheduled.yml` | 08:07 Tuesday–Saturday | `7 1 * * 2-6` | The previous Vietnam calendar day |

These replace the retired `stock-eod.yml` and `index-eod-v2.yml`. Schedules are in **UTC** and Vietnam is UTC+7 (no daylight saving time). GitHub Actions schedule starts may be delayed. To avoid silently ingesting an unintended session, scheduled runs use the **most recent elapsed configured Vietnam-local slot**, including when GitHub starts them after midnight or on a weekend. The Stock target is the slot date; the Index target is the day before its slot. The logs include `expected_slot_vn`, `runtime_vn`, `target_date`, and `target_source`. If a delayed run begins after the *next* scheduled slot, wall-clock-only resolution cannot recover the original intended date and may select the newer slot; inspect logs and use a manually entered date to recover missed sessions. An absent/dropped GitHub cron event is not automatically recovered. There is no automatic catch-up or holiday calendar; an empty SSI response must never create synthetic data.

Scheduled workflows resolve their target dates inside the workflow and always pass an explicit date to `python main.py stock-eod` or `python main.py index-eod`. Manual dispatch with an explicit `date` passes that date unchanged; manual dispatch with a blank date intentionally invokes the existing CLI **without** a date, preserving its original default-date behavior. The ingestion code and `src.ingest.workflows.workflow_dates` are not changed.

**Warning:** These are **one run per pipeline per trading session**, not two retries of the same dataset: Stock EOD runs that afternoon and Index EOD runs the next morning. The schedules assume a Monday–Friday market calendar and do not independently verify holidays, data freshness or completeness. The existing Stock EOD completeness check remains active. A repeat ingestion of the same date must be deliberately initiated; data reconciliation/idempotent update behavior remains governed by existing persistence rules.

Other workflows (`tests.yml`, `stock-intraday.yml`) are unchanged by this EOD change. No features, signals, backtests or index/stock cross-invocation are automatically triggered by the EOD workflows. `features.yml` is manual-dispatch only and is not invoked by them; its own input handling is described below.

## Manual feature dispatch (`features.yml`)

`features.yml` runs only on `workflow_dispatch` and executes `python main.py features --mode <mode>` with the existing CLI defaults. It does not ingest source data, generate signals, run backtests, or call the EOD workflows.

All four dispatch inputs reach the shell as environment variables (`DATE_INPUT`, `MODE_INPUT`, `SYMBOLS_INPUT`, `TIMEFRAMES_INPUT`); the run block contains no inline `${{ inputs.* }}` interpolation, no `eval`, and every argv array is quoted. Symbols/timeframes are split into quoted argv arrays, so shell metacharacters, quotes, `$`, backticks, `;` and globs are data, never commands.

| Input | Blank / whitespace-only | Non-blank |
| --- | --- | --- |
| `mode` | Falls back to `incremental` (same as the input and CLI default) | Always passed as `--mode`; `incremental` (default) or `full` |
| `date` | Omits `--date`, keeping the existing CLI default | Passed unchanged as one literal `--date` value |
| `symbols` | Omits `--symbols` (CLI default: all symbols); no bare `--symbols` | Split on spaces/tabs into `--symbols` values; no bare flag |
| `timeframes` | Omits `--timeframes`, so the current CLI default `15m 60m 1d` applies; no bare `--timeframes` and no empty timeframe list | Split on spaces/tabs into `--timeframes` values; no bare flag |

Inputs containing CR or LF are rejected before array splitting, so a multi-line value is never silently truncated to its first line. Any symbol/timeframe token starting with `-` (and an option-like `date` or `mode`) is rejected before Python runs, to prevent option injection. Unsupported symbols, dates and timeframes still fail through the existing CLI validation; the workflow adds no symbol/date format regex and does not enforce a timeframe allow-list of its own. If Python exits non-zero, the failing exit code is propagated to the job.

No migration, database rewrite or historical backfill is part of this workflow-only change.
