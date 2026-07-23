# Production source-data backfill

## Purpose and architecture

Backfill reruns the existing Phase 0 EOD source-data contract for an inclusive historical range:

```text
each weekday candidate
→ run_eod_pipeline(DD/MM/YYYY) exactly once
→ daily ingest
→ intraday 1m ingest
→ ingest completeness check
→ OK / PARTIAL / FAILED
```

Backfill contains no SSI fetch, mapping, validation, persistence, feature, signal, or backtest implementation. A weekday is only a calendar candidate; SSI empty responses on holidays or non-trading days remain visible in the delegated EOD summary and are never replaced with fabricated rows or zero values.

## CLI and examples

Both endpoints are required and inclusive:

```bash
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from-date DD/MM/YYYY --to-date DD/MM/YYYY
```

Example:

```bash
python main.py backfill --from 10/07/2026 --to 14/07/2026
```

Dates are parsed in the product's Vietnam-market date format. Future dates and reversed ranges are rejected. Calendar dates are visited sequentially; Saturdays and Sundays are skipped and reported in `skipped_weekend_dates`. A weekend-only range is a successful no-op with `processed_days=0` and `status=OK`.

## Data affected and reruns

An intentional run can affect exactly the same tables as sequential EOD commands: `raw_daily`, `stock_daily`, `index_daily`, related index master tables, `raw_intraday`, and `stock_intraday` with `timeframe='1m'`. Completeness validation reads the resulting source tables. Actual writes depend on SSI responses and the existing EOD services.

Existing persistence conflict keys make normal EOD reruns use the current idempotency contracts; backfill adds no alternative persistence behavior. Verify one historical trading date before expanding a range. No production backfill runs automatically after deployment.

Features, signals, and backtests **do not run automatically**. Run an explicit downstream pipeline only after source data and completeness have been verified.

## Summary and status contract

The JSON range summary contains `flow`, `from_date`, `to_date`, `requested_calendar_days`, `processed_days`, `skipped_weekend_days`, `skipped_weekend_dates`, `ok_days`, `partial_days`, `failed_days`, `error_count`, `errors`, `day_summaries`, and `status`. Successful EOD summaries are retained unchanged. An exception is caught at its date boundary, recorded with its date and message, and later dates continue.

- `OK`: every processed day is `OK` (including the documented zero-processed-day no-op).
- `FAILED`: every processed day is `FAILED`.
- `PARTIAL`: statuses are mixed, or at least one processed day is `PARTIAL`.

Exit codes are `0` for `OK` or `PARTIAL`, `1` for `FAILED` or an unhandled runtime failure, and `2` for invalid CLI arguments or date ranges.

## Compatibility and limitations

`src.pipeline.backfill.backfill(...)` remains as a deprecated wrapper. It accepts legacy ISO dates and optional symbol scope for import compatibility, converts dates, and delegates to `run_backfill_pipeline()`; future-date overrides remain rejected. `scripts/backfill_sample.py` is also deprecated and delegates to the production pipeline.

Backfill skips only weekends, not exchange holidays. It does not provide parallel execution, automatic retry beyond the bounded existing SSI/database client behavior, automatic feature computation, or a transaction spanning multiple dates. A date-level failure may leave the same partial writes as an interrupted EOD run; inspect the retained summary and rerun safely.

## Tests

```bash
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q
```

## Symbol scope

Use `--symbols SSI HPG` to apply one normalized explicit stock scope to every EOD date. Values are stripped, uppercased, and deduplicated in first-seen order; the option requires at least one value. Omission retains the existing all-master-symbol behavior. EOD applies the scope consistently to daily stock ingest, intraday ingest, and stock completeness, while daily index context remains independent. Summary fields expose `symbol_scope`, `requested_symbols`, `symbols`, and `symbol_count`.
