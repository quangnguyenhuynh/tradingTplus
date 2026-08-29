# Stock Daily EOD pipeline

`stock-eod` is the daily-only stock source pipeline. The independent workflow runs at 09:30 UTC (16:30 Asia/Ho_Chi_Minh), Monday-Friday, or by manual dispatch.

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

An omitted date resolves to the latest weekday on or before today in Vietnam; this calendar fallback does not prove an exchange trading session. An omitted symbol list uses `symbols.status='active'`. Explicit symbols are normalized and intersected with that same daily scope; inactive/unknown values are reported in `ignored_symbols`.

Stages are: resolve scope, SSI `DailyStockPrice`, raw `stock_raw_daily`, validated clean `stock_daily`, then `check_daily_ingest`. The final status uses daily evidence only. The deprecated `intraday_summary` compatibility key is `null`.

The pipeline never calls `IntradayOhlc`, reads/writes intraday or index data, or runs features, signals, backtests, Historical Analog, or automatic backfill.
