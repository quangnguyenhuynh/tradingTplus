# TradingTPlus CLI usage

This is the production command reference for Phase 0 data foundation and validation.

## Environment

Create `.env` with Supabase and SSI credentials. Do not commit real secrets.

Required variables used by production flows include `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SSI_CONSUMER_ID`, and `SSI_CONSUMER_SECRET`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Command completed with `OK` or `PARTIAL` summary. Review JSON for warnings. |
| `1` | Command returned `FAILED` or raised an unhandled runtime error. |
| `2` | Invalid CLI arguments or invalid date/scope. |

## Recommended operating order

```text
sync-master-data
→ daily
→ intraday-ingest
→ check/completeness or eod orchestration
→ features chạy riêng
```

## Quick distinction

| Command | Purpose | SSI ingest? | Tables written | Does not do |
| --- | --- | --- | --- | --- |
| `daily` | Stock daily source ingest | `DailyStockPrice` | `raw_daily`, `stock_daily` | market indexes, intraday candles, features, signals, backtests |
| `intraday-ingest` | 1m intraday candle ingest | `IntradayOhlc` resolution `1` | `raw_intraday`, `stock_intraday` (`timeframe='1m'`) | daily writes, foreign/index writes, features, signals, backtests |
| `intraday` | Legacy intraday feature alias | No | `features` via feature engine | SSI candle ingest, `1d` features |
| `eod` | Orchestrate Phase 0 EOD ingest/check | Daily then intraday | Same as `daily` + `intraday-ingest` | features, signals, backtests |
| `backfill-daily` | Inclusive stock-daily historical ingest | `DailyStockPrice` per weekday | `raw_daily`, `stock_daily` | market indexes, intraday, completeness, features, signals, backtests |
| `backfill-intraday` | Inclusive 1m intraday historical ingest | Once per weekday | Intraday raw/clean tables | daily, completeness, features, signals, backtests |
| `backfill` | Daily range then intraday range and completeness | Branches then per-date checks | Both source-data layers | features, signals, backtests |
| `features` | Explicit deterministic feature pipeline | No | `features` | source ingest, signals, backtests |

## `sync-master-data`

Syntax:

```bash
python main.py sync-master-data
```

Purpose: synchronize SSI master data.

Parameters: none.

Reads SSI: `Securities`, `SecuritiesDetails`, `IndexList`, and `IndexComponents`.

Writes: `symbols`, `securities`, `indexes`, `index_components`.

Does not: ingest daily history, ingest intraday candles, calculate features, generate signals, or run backtests.

Public function: `src.pipeline.init_symbols.init_symbols() -> None`.

## `init`

Syntax:

```bash
python main.py init
```

Purpose: backward-compatible alias for `sync-master-data`.

Parameters/defaults/read/write behavior: same as `sync-master-data`.

## `daily`

Syntax:

```bash
python main.py daily [DD/MM/YYYY] [--symbols SSI HPG]
```

Positional parameters:

- `date` optional, format `DD/MM/YYYY`; omitted means the repository's safe latest-previous-weekday default.

Default behavior: all active symbols from `symbols` are processed.

Reads DB: `symbols` when `--symbols` is omitted. Reads SSI: `DailyStockPrice` only (including daily foreign and room fields).

Writes: `raw_daily` and canonical `stock_daily` (including daily foreign and room fields). It does not call `DailyIndex`, `IndexList`, or `IndexComponents`; does not write `index_daily`, `indexes`, or `index_components`; and does not write the legacy `foreign_trading` table.

Does not: call SSI `DailyIndex`, `IndexList`, `IndexComponents`, or `IntradayOhlc`; write market-index or intraday tables; calculate features; generate signals; or run backtests.

Examples:

```bash
python main.py daily
python main.py daily 10/07/2026 --symbols SSI HPG
```

Public function: `src.pipeline.daily.run_daily_ingest(date: str | None = None, symbols: list[str] | tuple[str, ...] | None = None) -> dict`.

Summary fields include `date`, `symbol_count`, `daily_valid_count`, `total_daily_rows`, `total_foreign`, `index_daily_count`, `errors`, and `status`. `total_foreign` is retained temporarily for compatibility and is always `0`; `total_candles` and `index_daily_count` are also deprecated compatibility keys and are always `0`; none is populated by a DB query.

## `intraday-ingest`

Syntax:

```bash
python main.py intraday-ingest [DD/MM/YYYY] [--symbols SSI HPG]
```

Positional parameters:

- `date` optional, format `DD/MM/YYYY`; omitted means the same safe latest-previous-weekday default used by ingest commands.

Optional parameters:

- `--symbols`: optional list; values are normalized to uppercase. Omitted means all active symbols.

Reads: `symbols` when `--symbols` is omitted; optional `stock_daily` context for the same `symbol + trading_date`; SSI `IntradayOhlc` resolution `1`.

Writes: `raw_intraday`, `stock_intraday` with canonical persisted `timeframe='1m'`.

Does not: call SSI `DailyStockPrice`, `DailyIndex`, `IndexList`, `IndexComponents`, `Securities`, or `SecuritiesDetails`; write daily/index tables; calculate features; generate signals; or run backtests.

Missing daily context is reported as `daily_context_missing`; optional context fields remain `None` and are not replaced with zero.

Examples:

```bash
python main.py intraday-ingest
python main.py intraday-ingest 10/07/2026 --symbols SSI HPG
```

Public function: `src.pipeline.intraday_ingest.run_intraday_ingest(date: str | None = None, symbols: list[str] | tuple[str, ...] | None = None) -> dict`.

Summary fields include `date`, `symbol_count`, `candles_received`, `candles_valid`, `candles_rejected`, `daily_context_missing_count`, `daily_context_missing_symbols`, `errors`, `per_symbol`, and `status`.

## `eod`

Syntax:

```bash
python main.py eod [DD/MM/YYYY] [--symbols SSI HPG]
```

Positional parameters:

- `date` optional, format `DD/MM/YYYY`; omitted means latest weekday on or before the run date in VN date handling.

Flow:

```text
daily ingest
↓
intraday ingest 1m
↓
ingest completeness check
↓
OK / PARTIAL / FAILED
```

Reads/writes: stock-only `daily` plus stock-only `intraday-ingest`; completeness evaluates canonical `stock_daily` and `stock_intraday`. The deprecated `index_daily_count` is static `0` and completeness never queries `index_daily`.

Does not: calculate features, generate signals, or run backtests.

Example:

```bash
python main.py eod 10/07/2026 --symbols SSI HPG
```

Public function: `src.pipeline.eod.run_eod_pipeline(date: str | None = None, *, timeframes=None, symbols=None) -> dict`.

Summary fields include `daily_summary`, `intraday_summary`, `ingest_summary`, final `status`, `failures`, and `warnings`.

## Backfill commands

Syntax:

```bash
python main.py backfill-daily --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
python main.py backfill-intraday --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
python main.py backfill --from 01/07/2026 --to 10/07/2026 --symbols SSI HPG
```

All accept `--from-date`/`--to-date` aliases. Dates use `DD/MM/YYYY`; both endpoints are inclusive. Future/reversed ranges are rejected, weekends are skipped and reported, and a weekend-only range is an `OK` no-op. Weekday holidays are not guessed, so SSI empty responses remain observable.

`backfill-daily` calls only stock daily ingest (`DailyStockPrice`) per eligible date and never calls or writes market-index data. `backfill-intraday` calls only 1m intraday ingest and uses existing daily context if available; missing context remains `PARTIAL` and does not trigger daily ingest. Combined `backfill` runs the complete daily branch before the complete intraday branch, then checks scoped completeness for every eligible date. It retains both branch summaries and EOD-compatible combined day summaries; it no longer calls EOD directly.

None of these commands runs features, signals, or backtests. Exceptions are recorded by date and later dates continue. No backfill runs automatically after deployment.

Public functions:

- `run_daily_backfill_pipeline(from_date, to_date, symbols=None) -> dict`
- `run_intraday_backfill_pipeline(from_date, to_date, symbols=None) -> dict`
- `run_backfill_pipeline(from_date, to_date, symbols=None) -> dict`

See [the bilingual backfill guide](backfill/README.md).

## `features`

Syntax:

```bash
python main.py features --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m 1d
```

Parameters:

- `--mode`: `incremental` by default; `full` for historical reruns/backfills.
- `--date`: optional target date for incremental reruns.
- `--symbols`: optional symbol scope, normalized uppercase by CLI.
- `--timeframes`: optional feature timeframes.

Reads: `stock_daily` for `1d`, `stock_intraday` 1m for intraday aggregation, and existing feature context as implemented.

Writes: `features`.

Does not: ingest source data, generate signals, or run backtests.

Public function: `src.engine.feature_engine.run_feature_engine_with_summary(...) -> dict`.

## `intraday` legacy alias

Syntax:

```bash
python main.py intraday --symbols SSI HPG --timeframes 1m 5m 15m
```

Purpose: backward-compatible alias for incremental intraday feature calculation on already-ingested `stock_intraday` data.

Reads: existing `stock_intraday` and feature context.

Writes: `features` through the feature engine.

Does not: call SSI, ingest new candles, write `raw_intraday`/`stock_intraday`, or calculate `1d` features.

Public function: `src.pipeline.intraday.run_intraday_pipeline(snapshot_time: str | None = None, symbols: list[str] | None = None, timeframes: tuple[str, ...] = ('1m', '5m', '15m')) -> dict`.

## Shared source-ingest symbol scope

`daily`, `intraday-ingest`, `eod`, `backfill-daily`, `backfill-intraday`, and `backfill` use `--symbols` with `nargs="+"`; the flag therefore requires at least one value. Explicit values are stripped, uppercased, deduplicated, and retain first-seen order. Omitting the option uses every symbol returned by the existing master-symbol source; an explicit empty or blank-only programmatic scope raises `ValueError` rather than falling back to all symbols. Explicit symbols are not silently dropped against an invented active/inactive rule; existing per-symbol SSI/service results report unavailable symbols.

The scope limits stock ingest. Market-index ingest never runs; index master synchronization remains exclusive to `sync-master-data` / `init`. EOD passes the same scope to daily, intraday ingest, and stock-only completeness. Scoped completeness filters `stock_daily` and `stock_intraday`; deprecated `index_daily_count` is a static `0` and never triggers a DB query. All backfill branches reuse one normalized explicit list for every date; combined backfill passes it to both branches and completeness. None of these commands runs features, signals, or backtests. The legacy `intraday` command is a feature alias and is not production candle ingest.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.
