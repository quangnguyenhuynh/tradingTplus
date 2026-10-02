-- Promote SSI v3 stock-daily storage and provider-aware immutable raw identity.
-- Deployment: pause stock-daily writers while replacing the unique index. The
-- nullable clean column and raw columns are metadata-only before the bounded
-- backfill; no clean market values are rewritten or fabricated.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '5min';

alter table public.stock_daily
  add column if not exists foreign_total_room numeric;

alter table public.stock_raw_daily
  add column if not exists source text,
  add column if not exists fetched_at timestamptz;

update public.stock_raw_daily
set source = 'ssi_v2'
where source is null;

update public.stock_raw_daily
set fetched_at = created_at
where fetched_at is null;

alter table public.stock_raw_daily
  alter column source set not null;

drop index if exists public.stock_raw_daily_symbol_trading_date_data_hash_uidx;
create unique index if not exists stock_raw_daily_symbol_trading_date_source_data_hash_uidx
  on public.stock_raw_daily(symbol, trading_date, source, data_hash);

notify pgrst, 'reload schema';
commit;

-- Verification (read-only): inspect information_schema.columns for the three
-- added columns and pg_indexes for the four-column unique index above.
-- Rollback guidance: restore the old unique index only after proving that no
-- cross-source duplicate hashes exist. Keep additive columns to preserve data.
