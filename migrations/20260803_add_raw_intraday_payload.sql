-- Preserve the complete SSI candle object for new raw intraday ingest rows.
alter table public.raw_intraday
  add column if not exists payload jsonb;

comment on column public.raw_intraday.payload is
  'Original semantic SSI candle JSON object; historical rows may be NULL.';

-- Read-only verification:
-- select data_type, is_nullable
-- from information_schema.columns
-- where table_schema = 'public' and table_name = 'raw_intraday'
--   and column_name = 'payload';
-- Expected: jsonb, YES.

-- Rollback guidance (only if new payload data is intentionally disposable):
-- alter table public.raw_intraday drop column if exists payload;
-- This migration performs no historical backfill and does not rewrite old rows.
