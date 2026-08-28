# Stock EOD pipeline

## Purpose and schedule

`stock-eod` is the end-of-day **stock source-data** orchestrator. GitHub Actions runs `.github/workflows/stock-eod.yml` at 09:30 UTC (16:30 Asia/Ho_Chi_Minh) Monday through Friday, with manual dispatch available. It is separate from `.github/workflows/index-eod.yml`.

## Run manually

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

An omitted date resolves to the latest weekday on or before the current Vietnam date. This is a scheduling fallback, not proof that the date is an exchange trading day; completeness exposes empty or partial source results.

## Active symbol scope

The pipeline reads `symbols` with `status = 'active'`. With no `--symbols`, all active rows are used. Explicit values are stripped, uppercased, and deduplicated in first-seen order, then intersected with that active set. Inactive and unknown values are reported in `ignored_symbols` and are never ingested. One resolved list is passed unchanged to every stage.

## Ordered stages and data contracts

1. Stock daily ingest: SSI `DailyStockPrice` payload evidence to `raw_daily`, then normalized rows to `stock_daily`.
2. Stock intraday ingest: SSI `IntradayOhlc` payload evidence to `raw_intraday`, then canonical 1-minute rows to `stock_intraday`.
3. Stock completeness: read-only checks across the active scope and trading date.
4. Final stock-only status aggregation.

`SUCCESS` in operational descriptions corresponds to summary status `OK`: both stock datasets are present and no stage failed. `PARTIAL` means completeness reports missing/incomplete stock coverage without a total failure. `FAILED` means a stock stage failed, completeness failed, or required daily/intraday counts are zero.

## Explicit exclusions

Stock EOD does not call `DailyIndex`, read `index_master`, write `index_raw_daily`/`index_daily`, or run index completeness. Index data is handled independently by `index-eod`. Stock EOD does not compute features, signals, backtests, or Historical Analog output. “EOD” in Historical Analog remains a checkpoint name and is not renamed by this pipeline interface change.
