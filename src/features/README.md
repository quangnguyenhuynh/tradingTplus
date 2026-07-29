# Feature package

`common.py` owns shared deterministic math, nullable comparisons, the 35-column contract and serialization primitives. `daily.py` exposes daily calculation/execution; `intraday.py` exposes 1m preparation, observed-only aggregation, closed-bucket filtering and intraday execution; `runner.py` owns bounded pagination, symbol/error summaries and the deprecated mixed orchestrator. The old `src.engine.feature_*` modules are import-only compatibility shims.

## Sources and formulas

The daily flow reads `stock_daily` only and writes `features(timeframe='1d')`. Daily returns use `close/open-1` and the verified prior daily close. Daily rolling MA/high/low remain bar based. The intraday flow reads canonical `stock_intraday(timeframe='1m')`, and may read `stock_daily` only for same-date official `open_price` and previous `close_price`. It aggregates 5m/15m/60m in memory; timestamps are timezone-aware UTC bucket starts interpreted in `Asia/Ho_Chi_Minh`, never audit timestamps.

EMA uses pandas EWM `adjust=False` (spans 9/20/50); RSI14 is Wilder-style EWM (`alpha=1/14`, `adjust=False`); MACD is EMA12 minus EMA26 with EMA9 signal. Intraday EMA/RSI/MACD and preceding high/low20 continue across observed dates. VWAP resets daily. Intraday `volume_ma20`/`value_ma20` compare the current session/local bucket with the previous 20 observed dates and exclude the current bucket. Missing comparable buckets are not fabricated. Flags are true/false only with both inputs; otherwise they persist as NULL.

Intraday `return_from_open` uses official `stock_daily.open_price`; missing/invalid context remains NULL. Previous-close context also comes from `stock_daily`. Intraday value remains the estimate `round(close * volume)`, so VWAP is approximate, not exchange turnover VWAP.

## Execution

Full and incremental runs use all available prior history in Phase 0 so EWM outputs match on overlap (serialized numeric tolerance: 1e-6). Reads are paginated and stop at source exhaustion; logs report range, aggregated bars, observed dates and sufficiency. Incremental filters writes to its target date. Production writes exclude open buckets; an observed partial aggregate may exist only in memory. Session-ending short buckets close at the session boundary. Historical dates use the completed boundary; the current date uses Vietnam `now`, or safe `--as-of` (`HH:MM` on target date or timezone-aware timestamp).

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI HPG
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m
python main.py features-intraday --date 10/07/2026 --as-of 14:30 --symbols SSI
```

`features` remains a deprecated mixed router; `intraday` remains its incremental intraday alias. No feature command calls SSI, ingest, signals, backtests or alerts. All flows write only `features`, keyed by `(symbol,timeframe,time)`.

Migration `20260729_drop_legacy_feature_columns.sql` removes eight unused legacy columns. Apply it manually after review. Raw/clean data is unaffected. A manual full daily/intraday canonical backfill is required after deployment. Audit old possibly-open rows read-only and scope any cleanup separately.

Known limitations: exchange holidays/halts are observed from available data rather than a bundled exchange calendar; session boundaries are configured assumptions; missing source remains NULL; approximate value limits VWAP precision; feature runs are database writes and are not production smoke tests.
