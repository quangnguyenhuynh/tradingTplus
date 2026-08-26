-- Cleanup helper for accidental SSI smoke-test writes.
-- Replace values before running in Supabase SQL Editor.
-- Safe/idempotent: deleting non-existent rows is a no-op.

begin;

-- Required inputs (edit these literals):
--   symbol: SSI
--   trading_date: 2024-07-05
--   intraday timestamp window: 2024-07-05 00:00:00 to 2024-07-06 00:00:00

delete from public.stock_raw_daily
where symbol = 'SSI'
  and trading_date = date '2024-07-05';

delete from public.stock_daily
where symbol = 'SSI'
  and trading_date = date '2024-07-05';

-- Only needed if smoke test was run with --write-intraday.
delete from public.stock_raw_intraday
where symbol = 'SSI'
  and time >= timestamptz '2024-07-05 00:00:00+07'
  and time <  timestamptz '2024-07-06 00:00:00+07';

delete from public.stock_intraday
where symbol = 'SSI'
  and timeframe = '1m'
  and time >= timestamptz '2024-07-05 00:00:00+07'
  and time <  timestamptz '2024-07-06 00:00:00+07';

-- Optional: remove a daily index row for the same date if it was test-only.
-- delete from public.index_daily
-- where index_code = 'VNINDEX'
--   and trading_date = date '2024-07-05';

commit;
