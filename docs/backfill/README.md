# Production backfill

[English](README.md) | [Tiếng Việt](README.vi.md)

## Purpose

The production backfill command reruns the existing EOD ingest and completeness flow for an inclusive historical date range.

For every weekday, it delegates to `src.pipeline.eod.run_eod_pipeline()`:

```text
daily ingest
→ intraday 1m ingest
→ ingest completeness check
→ OK / PARTIAL / FAILED
```

Backfill is orchestration only. It does not duplicate daily or intraday fetch, mapping, validation, or persistence logic.

## CLI

```bash
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY
```

`--from-date` and `--to-date` are accepted as aliases.

Example:

```bash
python main.py backfill --from 01/07/2026 --to 10/07/2026
```

Start with a small range and review the JSON summary before running a longer range.

## Scope and safety

- Both dates are inclusive.
- Dates must use `DD/MM/YYYY` in the production CLI.
- Future dates are rejected.
- `--from` must be on or before `--to`.
- Saturdays and Sundays are skipped and listed in the summary.
- A range containing no weekdays is rejected.
- Weekdays are calendar candidates, not proof of an exchange trading day. The command does not fabricate rows for holidays or empty SSI responses; the delegated EOD result reports the actual outcome.
- The command processes the same full active-symbol universe as the current EOD pipeline. Symbol-scoped backfill is intentionally not exposed because EOD currently ignores symbol scope.
- Execution is sequential by date to keep writes and summaries bounded and explainable.

## Data read and written

Each processed date has the same data impact as:

```bash
python main.py eod DD/MM/YYYY
```

That includes the existing daily, intraday 1m, index, raw/clean persistence, and completeness paths already owned by EOD and its child pipelines.

Backfill never automatically calculates features, generates signals, or runs backtests.

## Summary contract

The command prints one JSON object with:

- `from_date`, `to_date`
- `requested_calendar_days`
- `processed_days`
- `skipped_weekend_days`, `skipped_weekend_dates`
- `ok_days`, `partial_days`, `failed_days`
- `errors`
- `day_summaries`, containing the unchanged EOD summary for every processed weekday
- final `status`

Final status rules:

- `OK`: every processed weekday returned `OK`.
- `FAILED`: every processed weekday returned `FAILED`.
- `PARTIAL`: any mixed result, or any processed weekday returned `PARTIAL`.

Exit codes follow the main CLI contract:

- `0`: `OK` or `PARTIAL`; inspect the JSON summary.
- `1`: final status `FAILED` or an unhandled runtime failure.
- `2`: invalid CLI arguments or invalid date range.

## Reruns

The command reuses existing persistence methods and conflict keys. Rerunning a scoped date range is therefore intended to update/reconcile the same raw and clean records rather than create feature, signal, or backtest side effects.

Before production use, verify that the deployed database contains the unique indexes required by the repository's current `on_conflict` keys.

## Deprecated wrapper

`scripts/backfill_sample.py` remains only as a compatibility wrapper and delegates to the same production pipeline. Prefer the main CLI.

## Tests

```bash
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q
```

SSI/Supabase smoke checks must remain explicitly scoped and read-only unless a production write is intentionally requested.

## Current limitations

- No exchange holiday calendar is inferred or fabricated.
- No symbol-scoped mode while EOD itself remains full-universe.
- No automatic retry of only failed dates after the range completes; rerun an explicit smaller range.
- No feature backfill is triggered. Run `python main.py features ...` separately only after source data has been verified.
