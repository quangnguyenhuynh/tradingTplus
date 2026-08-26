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
| `phase0_validate_schema.py` | `READ-ONLY` | Verify payload/RPC/index catalog contracts through a forced read-only PostgreSQL connection. |
| `phase0_reconcile_sample.py` | `READ-ONLY` | Check bounded payload lineage and one explicit raw/clean/feature sample with PASS/FAIL/UNKNOWN output. |
| `eod_dry_run.py` | `READ-ONLY` | Inspect EOD readiness without database writes. |
| `fetch_one_day.py` | `DRY-RUN DEFAULT` | Inspect or write exactly one symbol/day. |
| `backfill_sample.py` | `WRITES DB` | Deprecated delegate to combined production backfill; explicit inclusive dates required. |
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

Phase 0 closure checks require explicit scopes and never infer live evidence. Use
`PHASE0_DATABASE_URL=... python scripts/phase0_validate_schema.py` for catalog
metadata, and `python scripts/phase0_reconcile_sample.py --symbol SSI --date
YYYY-MM-DD --timeframe 1d` for reconciliation. The latter may also accept an
exact `--timestamp` for `15m`/`60m`. Historical NULL intraday payloads are
expected; no non-NULL sample yields `UNKNOWN`, not PASS.

Use `python main.py backfill-daily`, `backfill-intraday`, or combined `backfill` with explicit inclusive dates for production. The deprecated sample accepts optional `--symbols` but no future override, delegates to the same pipeline, skips weekends, and never runs features, signals, or backtests automatically. See [`docs/backfill/README.md`](../docs/backfill/README.md).

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `stock_features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.
