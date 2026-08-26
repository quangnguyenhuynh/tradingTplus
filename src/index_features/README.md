# Index Daily Feature V1

This package is a separate derived-data pipeline for market indexes. It reads
only normalized `index_daily` rows and writes only `index_features_daily`.
It does not ingest SSI data and never calls stock features, Analog, profiles,
signals, validation, or backtests. `VNINDEX` is the initial primary index, while
omitting `--indexes` follows the index CLI convention and resolves all rows in
`index_master`.

## Schema and formulas

The identity is `(index_code, trading_date)` with an FK to `index_master`.
`index_value`, `total_vol`, `total_val`, and calculated `breadth_total` retain
PostgreSQL `numeric` precision; deterministic ratios and indicators use `double
precision`. Audit timestamps are non-null. RLS permits service-side access and
does not grant `anon` or `authenticated` access.

Price features are lag returns for 1/3/5/10 sessions, SMA20/SMA50 and distance,
Wilder RSI14, MACD(12,26,9), 20-session return volatility, and 20/60-session
drawdown from the rolling maximum. Breadth uses
`advances + no_changes + declines`, net advances, component percentages, limit
balance, and 5/10-session means of breadth ratio. Liquidity uses 20-session
total volume/value means and ratios plus match/deal shares of source totals.
No OHLC, ATR, candle field, raw JSON, or missing session is synthesized.

Missing input remains `NULL`; valid zero counts remain zero. A zero or null
denominator produces `NULL`. Rolling results remain `NULL` until their complete
window exists. NaN and infinity are converted to `NULL`. Each calculation may
read up to 250 earlier clean trading sessions, then writes only its requested
date range, making incremental and backfill overlap deterministic.

## Operations

Apply `migrations/20260826_create_index_features_daily.sql` manually, then run:

```bash
python main.py index-features-preview --date 25/08/2026 --indexes VNINDEX
python main.py index-features-daily --date 25/08/2026 --indexes VNINDEX
python main.py index-features-backfill --from 05/01/2026 --to 25/08/2026 --indexes VNINDEX
python main.py index-features-check --from 05/01/2026 --to 25/08/2026 --indexes VNINDEX
```

Preview and check are read-only. Backfill clean `index_daily` first if a longer
history is required, then backfill index features, and finally run the check.
Raw-without-clean dates are reported and never become feature rows.
