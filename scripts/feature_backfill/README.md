# Feature Range Backfill

This CLI recomputes persisted features for an inclusive date range without ingesting SSI source data.

Production persistence remains limited to:

- daily: `1d`
- intraday: `15m`, `60m`

Clean `stock_intraday` 1m candles remain the canonical intraday source. No 1m or 5m feature rows are written.

## Daily range

```bash
python scripts/feature_backfill/run.py daily \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG
```

The runner reads `stock_daily` through the end date, computes indicators once with all earlier history available for warm-up, then upserts only `1d` feature rows whose dates fall inside the requested range.

## Intraday range

```bash
python scripts/feature_backfill/run.py intraday \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG \
  --timeframes 15m 60m
```

The runner reads clean 1m history through the end date, aggregates 15m/60m in memory, computes indicators once with prior history, then upserts only closed feature buckets inside the requested range.

## Difference from full and incremental

- `incremental`: write one target date.
- range backfill: write an inclusive `from`/`to` range.
- `full`: rewrite all feature history available in the source tables.

## Safety and limits

- This command writes only to `features`.
- It does not ingest raw or clean source data.
- It does not run signals or backtests.
- Reversed ranges and future end dates are rejected.
- Existing rows are upserted by `(symbol, timeframe, time)`.
- Start with a small symbol/date scope before expanding.

## Database impact

Migration: none.

Source tables are read-only for this command. No source-data backfill is required.
