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
| `daily` | Daily source ingest | `DailyStockPrice`, `DailyIndex` | `raw_daily`, `stock_daily`, `index_daily`, master index tables as needed | `foreign_trading`, intraday candles, features, signals, backtests |
| `intraday-ingest` | 1m intraday candle ingest | `IntradayOhlc` resolution `1` | `raw_intraday`, `stock_intraday` (`timeframe='1m'`) | daily writes, foreign/index writes, features, signals, backtests |
| `intraday` | Legacy intraday feature alias | No | `features` via feature engine | SSI candle ingest, `1d` features |
| `eod` | Orchestrate Phase 0 EOD ingest/check | Daily then intraday | Same as `daily` + `intraday-ingest` | features, signals, backtests |
| `features` | Explicit deterministic feature pipeline | No | `features` | source ingest, signals, backtests |

## `sync-master-data`

Syntax:

```bash
python main.py sync-master-data
```

Purpose: synchronize SSI master data.

Parameters: none.

Reads: SSI Securities/SecuritiesDetails/IndexList/IndexComponents, depending on current sync implementation.

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
python main.py daily [DD/MM/YYYY]
```

Positional parameters:

- `date` optional, format `DD/MM/YYYY`; omitted means the repository's safe latest-previous-weekday default.

Default behavior: all active symbols from `symbols` are processed.

Reads: `symbols`; SSI `DailyStockPrice` (including daily foreign and room fields); SSI `DailyIndex`; index master endpoints where needed.

Writes: `raw_daily`, canonical `stock_daily` (including daily foreign and room fields), `index_daily`, `indexes`, `index_components` as needed. Normal daily ingest does not write the legacy `foreign_trading` table.

Does not: call SSI `IntradayOhlc`, write `raw_intraday`/`stock_intraday`, calculate features, generate signals, or run backtests.

Examples:

```bash
python main.py daily
python main.py daily 10/07/2026
```

Public function: `src.pipeline.daily.run_daily_ingest(date: str | None = None) -> dict`.

Summary fields include `date`, `symbol_count`, `daily_valid_count`, `total_daily_rows`, `total_foreign`, `index_daily_count`, `errors`, and `status`. `total_foreign` is retained temporarily for compatibility and is always `0`; `total_candles` is also a deprecated compatibility key and is always `0` for daily-only ingest.

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

Does not: call SSI `DailyStockPrice`, write `raw_daily`/`stock_daily`, write `foreign_trading` or `index_daily`, calculate features, generate signals, or run backtests.

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
python main.py eod [DD/MM/YYYY]
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

Reads/writes: same as `daily` plus `intraday-ingest`; completeness reads canonical `stock_daily`, `stock_intraday`, `index_daily`, the legacy `foreign_trading` table, and related snapshot tables for counts. The legacy count is observability-only and is not a daily ingest write.

Does not: calculate features, generate signals, or run backtests.

Example:

```bash
python main.py eod 10/07/2026
```

Public function: `src.pipeline.eod.run_eod_pipeline(date: str | None = None, *, timeframes=None, symbols=None) -> dict`.

Summary fields include `daily_summary`, `intraday_summary`, `ingest_summary`, final `status`, `failures`, and `warnings`.

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
