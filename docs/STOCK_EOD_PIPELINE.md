# Stock Daily EOD pipeline

`stock-eod` is the daily-only stock source pipeline. The independent workflow runs at 16:30 Asia/Ho_Chi_Minh, Monday-Friday, or by manual dispatch.

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

An omitted date resolves to the latest weekday on or before today in Vietnam; this calendar fallback does not prove an exchange trading session. An omitted symbol list uses `symbols.status='active'`. Explicit symbols are normalized and intersected with that same daily scope; inactive/unknown values are reported in `ignored_symbols`.

The scheduled workflow does not omit the date. It resolves the latest Monday-Friday 16:30 Vietnam schedule slot and passes that slot's `DD/MM/YYYY` date explicitly. Consequently, a job intended for 05/10/2026 that starts after Vietnam midnight on 06/10/2026 still targets 05/10/2026. An explicit manual date wins unchanged; a manual dispatch without a date retains the CLI's calendar fallback. The workflow logs the event, actual Vietnam runtime, scheduled Vietnam slot, target date, and resolution source. GitHub Actions may start after its cron slot, so scheduled date selection must not use the delayed runner's wall-clock calendar date naively.

Stages are: resolve scope, resolved SSI daily source (v3 `securities-summary` by default; v2 `DailyStockPrice` only as deprecated explicit fallback), raw `stock_raw_daily`, validated clean `stock_daily`, then `check_daily_ingest`. The final status uses daily evidence only. The deprecated `intraday_summary` compatibility key is `null`.

The pipeline never calls `IntradayOhlc`, reads/writes intraday or index data, or runs features, signals, backtests, Historical Analog, or automatic backfill.

## Current-run completeness and canonical provenance

Stock EOD completeness reports both canonical presence and rows updated since the run began. A row is current-run complete only when its `updated_at` is current and its `source` matches the resolved provider.

`stock_daily.source` is persistence provenance rather than an SSI market-data contract field. `ssi_v3` means the current canonical row was last successfully written from SSI v3, while `ssi_v2` means it was last successfully written by the explicit deprecated fallback. `NULL` is retained for historical rows whose provider cannot be reconstructed safely; it must not be interpreted as v2. A response containing multiple provider records for one symbol/date retains each raw record but writes no ambiguous canonical row.
