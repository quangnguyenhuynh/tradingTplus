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

Value is source-specific: SSI v3 intraday preview preserves `ohlc.value` as exact BIGINT with no calculated fallback; missing/null stays NULL with diagnostics and malformed values reject. Historical rows and legacy callers may use `round(close * volume)` estimates; they are not relabeled or rewritten. SSI turnover semantics are not independently certified.

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

Feature aggregates retain `stock_intraday.time` as the UTC-represented Vietnam bucket start. Production feature writes require the bucket to be closed at the applicable session boundary; an observed partial aggregate is never proof of closure.

## Foreign EOD Feature V1

See [`docs/FOREIGN_EOD_FEATURES.md`](FOREIGN_EOD_FEATURES.md) for the approved dedicated table, formulas, calendar/freshness contract, RPC security, CLI, and manual rollout.

## Multi-page SSI v3 intraday preview (read-only)

The REST inspector stock-intraday/native intraday-ohlc routes now use the shared preview adapter and download successive pages from the requested start until explicit termination or failure/bound. `--limit` limits display only; `--full-json` includes every received raw page and clean candidate. `--max-pages` defaults to 100 (1–1000); hitting the bound, repeated pages, inconsistent totals or request failures return FAILED/exit 1 and retain received evidence. Other daily/index/catalog inspector routes keep their single-page behavior.

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Unattended ingestion/scheduling remains disabled; the inspector preview performs zero database reads/writes. The isolated manual pilot requires explicit --write; diagnostics never invoke it.

See the [runbook and promotion checklist](STOCK_INTRADAY_PIPELINE.md) for field mappings, paging, validation/session/gap rules, source limitations and separate promotion steps.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

## SSI v3 Phase 0 lineage reconciliation

Reconciliation only SELECTs persisted raw/clean/features in one symbol/Vietnam-date scope; it never ingests or computes features. Only `ssi_v3` uses the existing mapper; legacy `SSI` with separate TradingDate/Time/Value semantics is not reinterpreted as v3. Timestamps compare exact UTC instants with seconds retained; --timestamp never picks a nearby row. Intraday volume/value compare exact integers without float/tolerance; OHLC uses explicit tolerance. NULL stays NULL, with no close*volume estimate/zero fill; incomplete aggregate inputs are UNKNOWN before reaching legacy helpers. 1m needs no feature; 15m/60m follow existing left bucket/date/session/closure rules without a fixed emitted-bar count. PASS is verified equality, FAIL a verified contradiction, UNKNOWN missing/ambiguous/unsupported evidence; UNKNOWN never hides FAIL. Completeness OK covers structural checks only, not every market minute. No schema/data/backfill changes. [Runbook](../scripts/checks/README.md).
