# Foreign EOD features and reports

The independent flow is `stock_daily -> foreign feature command -> stock_foreign_features_daily -> RPC -> CLI/web/mobile`. Ingest never invokes it. DailyStockPrice fields already normalized in `stock_daily` are the only source; there is no separate public ForeignTrading REST endpoint.

## Formula V2 and row windows

For symbol S and target date D, the calculator selects only S rows with `trading_date <= D`, rejects duplicate `(symbol, trading_date)` rows, orders them by date, and uses the final N rows including D. Thus **N sessions means N `stock_daily` rows for that symbol**, not N calendar days, weekdays, an exchange-wide union, or dates inferred from another symbol. A target preview/daily run requires S to have a row exactly on D. A backfill emits only dates on which S has a source row.

For W=5 or 20, B/S/N/V mean foreign buy value, foreign sell value, validated source net value, and `total_traded_value`:

* net value = `SUM(N)`; activity value = `SUM(B+S)`;
* net ratio = `SUM(N)/SUM(V)`; activity ratio = `SUM(B+S)/(2*SUM(V))`;
* buy/sell days count N>0/N<0; zero belongs to neither;
* 5D changes subtract the preceding non-overlapping five-row ratio from the current five-row ratio, requiring 10 rows rather than 20.

Money is VND and ratios are fractions. A present row with a NULL/invalid required field still occupies its row position; it is never dropped, zero-filled, or forward-filled. The affected metric is NULL with a quality reason. A zero/invalid denominator yields a NULL ratio. Five-row metrics can be valid while 20-row metrics report `INSUFFICIENT_HISTORY`. Volume quality does not invalidate value metrics when their value inputs are valid.

Formula version 2 fingerprints the symbol, target, formula version, and all value/volume fields in the at-most-20 actual rows that affect metrics or quality. It excludes calendars, other symbols, and older rows. Recalculation upserts all metric columns, including explicit NULLs, under the existing `(symbol, trading_date)` key.

## Warm-up, incremental runs, and checks

Backfill loads at most 19 preceding rows **per symbol** and writes only the requested range. Incremental mode reviews the last 20 source rows for each symbol ending at the requested date and detects missing rows, V1/other formula versions, and changed fingerprints. A correction outside that bounded review requires a separately scoped backfill. A changed row can affect that row and up to the next 19 rows of the same symbol.

Preview, target, backfill, incremental, and check use the same loader/calculator. Check is read-only and compares source-derived V2 rows with persisted version/fingerprint; it does not ingest, repair, or backfill. Source and persisted-feature loaders use stable ordering and complete pagination.

`--calendar-file` remains temporarily accepted only for command compatibility. It emits `DEPRECATED_CALENDAR_FILE_IGNORED`, is never opened, and cannot affect results. `WINDOW_UNVERIFIED` is not part of V2 calculation.

## CLI

```bash
python main.py foreign-features-preview --help
python main.py foreign-features-backfill --help
python main.py foreign-features-preview --symbol SSI --date 28/08/2026 --show-source
python main.py foreign-features-backfill --from 03/08/2026 --to 28/08/2026 --symbols SSI --dry-run
python main.py foreign-features-backfill --from 03/08/2026 --to 28/08/2026 --symbols SSI
python main.py foreign-features-check --from 03/08/2026 --to 28/08/2026 --symbols SSI
python main.py foreign-rank --date 28/08/2026 --ranking accumulation --window 5 --symbols SSI --top 20
python main.py foreign-rank --date 28/08/2026 --ranking emerging --window 5 --sort value --symbols SSI --top 20
python main.py foreign-symbol --symbol SSI --date 28/08/2026 --lookback 20
python main.py foreign-features-daily --date 28/08/2026 --symbols SSI SHB --dry-run
```

Preview/check/rank/history never write. `--show-source` exposes the calculator's exact source rows and per-window/current-vs-previous dates. Daily/backfill `--dry-run` uses the normal loader, calculator, and validation but never calls persistence; `would_write` is reported and `written=0`. Omitting `--dry-run` on daily/backfill writes derived rows only.

## RPC migration and rollout

The table was introduced by `20260907_create_stock_foreign_features_daily.sql`. Deploy `20260923_foreign_features_symbol_rows_v2.sql` to replace both RPC definitions without changing their names/signatures or privilege boundary. The V2 ranking excludes old feature versions. Emerging value and ratio derive the current five and preceding five source rows directly, so they require 10 valid source rows plus the V2 target feature, not a prior persisted feature or 20 rows. Rankings remain fixed to the requested date. History marks non-V2 rows `STALE_FORMULA`.

Pulling application code does **not** update database RPCs. Recommended order: deploy the V2 migration and code in a coordinated window; preview a small scope; run a scoped V2 feature backfill; run check; then verify ranking/history RPCs. Do not apply migrations or write production rows automatically. Existing correct `stock_daily` does not need re-ingestion. Verification SQL and rollback guidance are in the migration.
