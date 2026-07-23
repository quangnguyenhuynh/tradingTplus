# Manual, smoke, and maintenance scripts

The `scripts/` directory contains explicit operational tools. These are not the primary production entrypoints; production flows should normally run through `main.py`.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- REST inspector: [ssi_api_inspector/README.md](ssi_api_inspector/README.md)
- Streaming inspector: [ssi_streaming_inspector/README.md](ssi_streaming_inspector/README.md)

## Safety labels

| Label | Meaning |
| --- | --- |
| `READ-ONLY` | Reads API/database state without writes. |
| `DRY-RUN DEFAULT` | Writes only after an explicit `--write`. |
| `WRITES DB` | Persists data when run; scope must be reviewed first. |

## Main scripts

| Script | Safety | Purpose |
| --- | --- | --- |
| `check_supabase.py` | `READ-ONLY` | Verify Supabase configuration and readable core tables. |
| `check_ssi_ingest_schema.py` | `READ-ONLY` | Check required SSI ingest tables/columns. |
| `check_complete_ssi_ingest.py` | `DRY-RUN DEFAULT` | Inspect SSI payloads and raw/clean mappings for a scoped symbol/date. |
| `check_ingest.py` | `READ-ONLY` | Report ingest completeness for a date. |
| `eod_dry_run.py` | `READ-ONLY` | Inspect EOD readiness without database writes. |
| `fetch_one_day.py` | `DRY-RUN DEFAULT` | Inspect or write exactly one symbol/day. |
| `backfill_sample.py` | `WRITES DB` | Deprecated delegate to EOD-based production backfill; explicit inclusive dates required. |
| `run_features.py` | `WRITES DB` | Run the feature pipeline explicitly. |
| `snapshot_stream.py` | `DRY-RUN DEFAULT` | Capture bounded streaming snapshots. |
| `snapshot_orderbook.py` | `DRY-RUN DEFAULT` | Capture quote/orderbook snapshots from supported streaming payloads. |

## Recommended order

```text
1. check_supabase.py
2. check_ssi_ingest_schema.py
3. use an SSI inspector when raw payload verification is needed
4. check_complete_ssi_ingest.py in read-only mode
5. fetch_one_day.py --dry-run
6. run a scoped ingest/write operation
7. check_ingest.py or eod_dry_run.py
8. run features separately after raw/clean/completeness verification
```

## Rules

- Do not connect ingest → features → signals → backtests inside a convenience script.
- A write script must require explicit symbol/date scope.
- Do not print secrets, tokens, or `.env` contents.
- Do not fabricate rows for weekends, holidays, empty responses, or unsupported endpoints.
- `stock_intraday` stores only `1m`; higher feature timeframes are aggregated later.
- Do not evaluate profitability while Phase 0 data remains unverified.

Run commands from the repository root and use `--help` before any write-capable tool.

Use `python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY` for production. The deprecated sample has no symbol/future override, delegates to the same pipeline, skips weekends, and never runs features, signals, or backtests automatically. See [`docs/backfill/README.md`](../docs/backfill/README.md).
