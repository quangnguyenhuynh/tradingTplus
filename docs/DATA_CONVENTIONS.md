# Data Conventions

## Purpose

This document defines data conventions for TradingTPlus Phase 0. It protects raw
and clean data correctness and guides future work on features, signals,
backtests, completeness validation, and alerts. These conventions describe data
meaning; they do not authorize a schema change or a data rewrite.

## Source of truth

- Raw data preserves SSI/API payloads and ingest traceability.
- Clean data contains normalized rows for research and feature pipelines.
- `stock_daily` is the canonical daily source for `1d` features.
- `stock_intraday` stores only clean `1m` candles.
- Higher intraday timeframes such as `5m`, `15m`, and `60m` are derived from
  `stock_intraday` during feature computation.
- Do not derive canonical `1d` features from intraday candles.

## Time and timezone conventions

- Use `Asia/Ho_Chi_Minh` for Vietnam market-session interpretation and
  user-facing trading times.
- PostgreSQL/Supabase may display `timestamptz` values in UTC. A UTC display does
  not mean the candle time is wrong.
- `stock_intraday.time` is the market/candle timestamp.
- `stock_intraday.time` is the source of truth for intraday ordering,
  aggregation, completeness, features, signals, backtests, and live alerts.
- `2026-07-15T02:15:00+00:00` equals
  `2026-07-15 09:15:00 Asia/Ho_Chi_Minh`.
- Keep timestamps timezone-aware. Do not convert timestamps to naive datetimes.
- Do not store market timestamps as text just to make them visually match
  Vietnam time.
- Do not manually add seven hours. Use timezone conversion.

Correct Python conversion with pandas:

```python
time_utc = pd.to_datetime(df["time"], utc=True)
time_vn = time_utc.dt.tz_convert("Asia/Ho_Chi_Minh")
```

Use the converted Vietnam timestamp to derive a trading date, assign a market
session, display a trading time, or enforce session boundaries. Retain an aware
UTC timestamp for stable storage, comparison, and serialization where the
pipeline contract requires UTC.

## Market timestamps and audit timestamps

Market timestamps describe when market data applies. Audit timestamps describe
when the application fetched, received, created, updated, or calculated a row.
They are not interchangeable.

| Column | Meaning | Valid market-time use |
| --- | --- | --- |
| `stock_intraday.time` | Intraday market/candle timestamp | Ordering, aggregation, completeness, features, signals, backtests, and alerts |
| `created_at` | First application insert time | Audit only |
| `updated_at` | Latest application upsert time | Audit only |
| `fetched_at` | Raw fetch time | Ingest traceability only |
| `received_at` | Streaming receipt/capture time | Transport and capture audit only; not a substitute for a source market timestamp |
| `last_updated_at` | Feature calculation/upsert time | Feature freshness audit only |

Never infer candle order, trading date, bar membership, signal time, backtest
entry/exit time, or alert market time from an audit timestamp. A delayed retry or
backfill can make an audit timestamp much later than the market event.

## Trading dates, sessions, and aggregation

- Resolve trading dates in `Asia/Ho_Chi_Minh`, not from the UTC calendar date
  alone.
- A weekday is not proof of a trading session; holidays, halts, shortened
  sessions, auctions, and missing source responses must be handled explicitly.
- Aggregate higher intraday timeframes from clean `stock_intraday` `1m` candles.
- Do not aggregate across Vietnamese trading dates, session boundaries, or the
  lunch break.
- Define whether an aggregate timestamp represents bar start or bar end before
  relying on it, and apply that convention consistently.
- Live and alert calculations must use closed candles or explicitly mark an
  incomplete candle.

## Missing and invalid data

- Do not fabricate rows for weekends, holidays, empty responses, or unsupported
  endpoints.
- Do not silently replace missing prices, volume, value, or flow with zero.
- Do not forward-fill OHLCV unless an explicit research contract requires it.
- Parse source timestamps explicitly. Reject or quarantine invalid timestamps;
  never replace one with the current time or an audit timestamp.
- Completeness is evaluated by symbol, Vietnam trading date, expected session,
  and source/timeframe. No universal candle count proves completeness.

## Units and provenance

Record and preserve whether a field is exchange-provided or derived. Do not mix
per-candle volume with cumulative volume, and do not compare values with
different units without normalization.

For current normalized intraday rows, `value` is the estimate
`round(close * volume)`. It is not exact exchange-provided turnover. Preserve
`NULL` when `close` or `volume` is invalid or missing; do not replace it with
zero.

## Downstream use checklist

Before implementing completeness, feature, signal, backtest, or live-alert work:

1. Use the correct canonical table and market timestamp.
2. Parse timestamps as timezone-aware and convert to `Asia/Ho_Chi_Minh` for
   trading-date and session logic.
3. Exclude audit timestamps from market chronology.
4. Respect symbol, trading-date, session, lunch-break, and timeframe boundaries.
5. Preserve missing/unsupported states and provenance.
6. Prevent look-ahead use of future candles or audit information.
7. Test UTC/Vietnam-equivalent timestamps, date boundaries, session boundaries,
   reruns, and backfills.

These rules are documentation only. They require no migration, data change, or
backfill.
