-- Backfill trading value for legacy intraday rows.
-- SSI intraday candles provide per-bar OHLC + volume, so value is close * volume.
UPDATE stock_intraday
SET value = close * volume
WHERE value IS NULL
  AND close IS NOT NULL
  AND volume IS NOT NULL;
