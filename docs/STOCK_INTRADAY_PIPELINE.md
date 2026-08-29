# Stock Intraday pipeline

`stock-intraday` is the independent automatic 1-minute stock source pipeline. `.github/workflows/stock-intraday.yml` runs at 10:00 UTC (17:00 Asia/Ho_Chi_Minh), Monday-Friday, and supports manual `date` and space-separated `symbols` inputs.

```bash
python main.py stock-intraday [DD/MM/YYYY] [--symbols SSI HPG]
```

## Scope and date

Automatic scope requires both `symbols.status='active'` and `symbols.intraday_status='active'`. Explicit workflow/CLI symbols are stripped, uppercased, deduplicated in first-seen order, and intersected with that effective scope. Inactive or unknown values appear in `ignored_symbols` and are never sent to SSI. No resolved symbol is a clear `FAILED` result.

An omitted date uses the latest weekday on or before today in Vietnam, so the after-close action targets the current weekday. This is not a holiday calendar; empty SSI responses remain empty and observable.

## Stages and tables

1. Resolve effective intraday scope.
2. Fetch SSI `IntradayOhlc` resolution 1.
3. Write source payloads to `stock_raw_intraday`.
4. Validate and upsert canonical `timeframe='1m'` candles to `stock_intraday`.
5. Run intraday-only completeness for presence, duplicates, first/last candle, morning/afternoon coverage, missing intervals, and structural gaps.
6. Aggregate the intraday stage status.

SSI may omit no-trade minutes, so short gaps are warnings/observations rather than a universal candle-count failure. No fake candles are created.

The pipeline does not ingest daily/index data or run features, signals, backtests, Historical Analog, or automatic historical repair. Daily database context may be read by the mapper; missing context is reported. Explicit `backfill-intraday`, combined `backfill`, and `refill` remain repair tools and can process an explicitly supplied inactive symbol.

Operators enable or disable future automatic intraday runs by updating `symbols.intraday_status` to `active` or `inactive`; daily must also remain active for effective automatic eligibility. No market-data backfill occurs when toggling it.
