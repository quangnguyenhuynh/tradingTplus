# Data pipelines

Production orchestration for master data, daily/intraday ingest, EOD validation, features compatibility, backfill, and bounded snapshots.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Main flows

| File/flow | Current responsibility |
| --- | --- |
| `init_symbols.py` | Synchronize symbols, securities, indexes, and index components. |
| `daily.py` | Daily SSI ingest only: `raw_daily`, `stock_daily`, foreign fields, and `index_daily`. |
| `intraday_ingest.py` | SSI `IntradayOhlc` resolution 1 into `raw_intraday` and `stock_intraday`. |
| `eod.py` | Daily ingest → intraday ingest → completeness check. |
| `fetch_one_day.py` | Scoped mapping helpers for one symbol/date. |
| `ingest_check.py` | Completeness summaries and missing-data reporting. |
| `date_utils.py` | Vietnam-market date parsing and safe-write checks. |
| `foreign_trading.py` | Derive foreign-trading records from `DailyStockPrice` fields. |
| `index_data.py` | Index master and daily index ingest. |
| `backfill.py` | Explicit scoped historical ingest. |
| `intraday.py` | Legacy intraday feature compatibility flow; not candle ingest. |
| `streaming_snapshot.py` | Bounded streaming capture; read-only unless write is explicit. |
| `orderbook_snapshot.py` | Quote-stream orderbook snapshot mapping. |
| `eod_dry_run.py` | Read-only EOD readiness checks. |

## Required separation

```text
daily ingest ─┐
              ├─> EOD completeness (optional orchestration)
intraday ingest┘

validated clean data ─> explicit feature pipeline
features ─> explicit signal/backtest jobs only when requested
```

## Data rules

- Daily canonical source: SSI `DailyStockPrice` → `stock_daily`.
- `DailyOhlc` is for inspection/cross-checking, not production daily ingest.
- Intraday persisted timeframe: `1m` only.
- Foreign trading is derived from fields in `DailyStockPrice`; do not invent a public standalone REST endpoint.
- Orderbook data comes from supported quote streaming or an explicitly configured private endpoint; unsupported data must be reported, not fabricated.
- Do not hardcode one candle count as universal completeness.

## Errors and writes

Use bounded retries, preserve symbol/date/timeframe/endpoint context, reject invalid timestamps, and do not swallow exceptions. Write-capable paths require clear scope and idempotent conflict keys.

## Tests

Relevant tests include CLI, daily/EOD, one-day mapping, intraday ingest, streaming ingest, completeness, and dry-run suites under `tests/`.
