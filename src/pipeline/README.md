# Data pipelines

Production ingest is split into explicit fetch, mapping, validation-integration, persistence, and orchestration layers. Daily and intraday are independent pipelines; EOD only sequences them and checks completeness.

## Directory tree and responsibilities

```text
src/pipeline/
├── daily_fetcher.py          # call SSI DailyStockPrice only
├── daily_mapper.py           # payload -> raw_daily / stock_daily records
├── daily_persistence.py      # raw_daily / stock_daily DB writes only
├── daily_service.py          # fetch -> map -> validate -> persist for one symbol/date
├── daily.py                  # public batch daily orchestrator
├── intraday_fetcher.py       # call SSI IntradayOhlc resolution 1 only
├── intraday_mapper.py        # payload -> raw_intraday / stock_intraday 1m records
├── intraday_persistence.py   # raw_intraday / stock_intraday DB writes only
├── intraday_service.py       # fetch -> map -> validate -> deduplicate -> persist
├── intraday_ingest.py        # public batch intraday orchestrator
├── fetch_one_day.py          # thin backward-compatibility wrapper/re-exports
├── eod.py                    # daily -> intraday -> completeness orchestration
├── ingest_check.py           # completeness and consistency report
├── date_utils.py             # Vietnam-market date parsing/safety
├── init_symbols.py           # master-data synchronization
├── index_data.py             # index master/daily ingest
├── foreign_trading.py        # legacy explicit compatibility writer; not normal daily ingest
├── backfill.py               # independent daily/intraday ranges + combined completeness
├── intraday.py               # legacy feature alias; not candle ingest
├── eod_dry_run.py            # read-only EOD/feature preview utility
├── streaming_snapshot.py     # bounded streaming capture
└── orderbook_snapshot.py     # quote-stream orderbook mapping
```

Existing streaming, index, master-data, feature-compatibility, and dry-run modules remain separate from the daily/intraday REST ingest layers.

## Daily execution

Public entrypoint: `daily_run()` / `run_daily_ingest()` in `daily.py`, exposed by `python main.py daily [DD/MM/YYYY] [--symbols SSI HPG]`.

1. Resolve and validate the requested Vietnam-market date.
2. `daily_fetcher.py` calls SSI `DailyStockPrice` once per symbol.
3. `daily_mapper.py` creates the source-preserving `raw_daily` record and normalized `stock_daily` candidate. Missing source fields remain `None`.
4. `daily_service.py` persists raw evidence through `daily_persistence.py`.
5. `daily_service.py` invokes the existing `validate_daily_record` validator.
6. Only valid clean candidates are persisted to `stock_daily` through `daily_persistence.py`.
7. Daily foreign buy, sell, net, and room fields remain part of the canonical `stock_daily` row; normal daily ingest does not write `foreign_trading`.
8. `daily.py` never calls `DailyIndex`, `IndexList`, or `IndexComponents`, and never writes `index_daily`, `indexes`, or `index_components`.

`foreign_trading` is retained as legacy historical storage and for the explicit compatibility helper only. Intraday foreign snapshots remain a separate streaming dataset and are unchanged by daily ingest.

## Intraday execution

Public entrypoint: `run_intraday_ingest()` in `intraday_ingest.py`, exposed by `python main.py intraday-ingest [DD/MM/YYYY] [--symbols ...]`.

1. Resolve date and explicit/all-active symbol scope.
2. Read optional daily context from `stock_daily`; this does not fetch or write daily data.
3. `intraday_fetcher.py` calls SSI `IntradayOhlc` with resolution 1.
4. `intraday_mapper.py` treats source candle times as `Asia/Ho_Chi_Minh`, converts them to UTC, rejects invalid timestamps, and creates raw and clean candidates.
5. The mapper persists only `timeframe='1m'`; `value` is the estimated `round(close * volume)` and remains `None` when either input is missing/invalid.
6. `intraday_service.py` persists raw evidence through `intraday_persistence.py`, invokes existing record/batch validators, deduplicates by `(symbol, timeframe, time)` when reported, then persists valid clean records.

Higher intraday timeframes are feature-time aggregations and are never written to `stock_intraday`.

Intraday gap validation normalizes timestamps to minute buckets in memory only; raw and clean timestamps are not modified. Empty/missing buckets are checked only within the continuous matching ranges `09:00-11:29` and `13:00-14:29` (`Asia/Ho_Chi_Minh`). Lunch-break minutes and the `14:30-14:44` ATC interval before an SSI close result around `14:45` are excluded. Input is sorted internally for gap checks while unsorted input remains explicitly reported.

`INTRADAY_MISSING_INTERVAL` means an **observed empty/missing minute bucket**. IntradayOhlc alone cannot distinguish a no-trade minute from a source omission. Short isolated gaps are therefore counted in `missing_interval_count`, `missing_minutes`, and `empty_minute_bucket_count` but do not by themselves fail completeness or fabricate candles. Duplicates and structural coverage problems still produce `WARNING`/`PARTIAL`. The initial structural heuristics are explicit data-quality thresholds, not official SSI rules: a continuous gap of at least 15 minutes, at least 30 total empty minutes, a missing morning/afternoon session, or first/last coverage more than 15 minutes inside the expected edges. No universal candle count is used.

## EOD execution

Public entrypoint: `run_eod_pipeline()` in `eod.py`, exposed by `python main.py eod [DD/MM/YYYY] [--symbols SSI HPG]`.

```text
daily ingest -> intraday ingest -> ingest completeness check -> OK/PARTIAL/FAILED
```

EOD preserves the daily and intraday service boundaries. It does not calculate features and does not run signals or backtests.

## Backfill execution

`run_daily_backfill_pipeline()` and `run_intraday_backfill_pipeline()` independently run only their source ingest for each eligible weekday. `run_backfill_pipeline()` runs the complete daily range, then the complete intraday range, then scoped completeness per date; it does not call EOD directly. All ranges are inclusive, report weekends, isolate date failures, and never run downstream engines. See [`docs/backfill/README.md`](../../docs/backfill/README.md).

## Raw, clean, validation, and persistence ownership

| Dataset | Record creation | Validation integration | Persistence |
| --- | --- | --- | --- |
| `raw_daily` | `daily_mapper.py` | raw evidence is retained before clean validation | `daily_persistence.py` |
| `stock_daily` | `daily_mapper.py` | `daily_service.py` + existing daily validator | `daily_persistence.py` |
| `raw_intraday` | `intraday_mapper.py` | raw evidence is retained before clean validation | `intraday_persistence.py` |
| `stock_intraday` | `intraday_mapper.py` | `intraday_service.py` + existing intraday validators | `intraday_persistence.py` |

## Compatibility wrapper

`fetch_one_day.py` remains a thin compatibility module for existing imports and the explicitly scoped script. It re-exports legacy mapper/fetcher helpers and composes the public daily and intraday services; it contains no duplicate mapping, validation, or persistence implementation. New code should import the relevant layered module directly.

The legacy `backfill(...)` import is deprecated and delegates to `run_backfill_pipeline()`; the optional legacy symbol scope delegates to production backfill; future overrides are rejected.

## Errors and retries

- Fetchers expose SSI client results and do not swallow service/DB failures.
- Empty SSI responses produce no fabricated raw or clean rows.
- Invalid timestamps are rejected rather than replaced with current time.
- Per-symbol services attach symbol/date context and return the existing summary contract.
- Bounded SSI HTTP retry behavior stays in `src/ssi/api.py`; bounded DB retry/backoff stays in `src/database/client.py`.
- Persistence continues using existing public DB methods and conflict keys.

## Tests

```bash
python -m pytest -q tests/ingest/test_fetch_one_day.py
python -m pytest -q tests/ingest/test_intraday_ingest_pipeline.py
python -m pytest -q tests/validation/test_intraday_validator.py
python -m pytest -q tests/ingest/test_ingest_check.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q
```

Ingest commands never automatically calculate features, generate signals, or run backtests. Those remain explicit downstream commands.

## Shared stock-symbol scope

`daily`, `intraday-ingest`, `eod`, completeness, `backfill-daily`, `backfill-intraday`, and `backfill` share one normalization contract: omitted scope uses the existing master-symbol source; explicit values are stripped, uppercased, deduplicated in first-seen order, and an empty explicit scope raises `ValueError`. Explicit symbols are preserved rather than silently dropped because the repository has no separate reliable active/inactive validation contract. EOD passes the same scope to all three source steps, scoped completeness filters stock rows at the database query, and backfill reuses the normalized scope for every date. The deprecated `index_daily_count` is always `0` without a DB query; index master synchronization remains exclusive to `sync-master-data` / `init`.
