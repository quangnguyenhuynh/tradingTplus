-- Application-controlled write timestamps for TradingTPlus pipelines.
-- Additive and idempotent: no historical rows are rewritten or deleted.

alter table if exists public.raw_daily
    add column if not exists created_at timestamptz default now();
alter table if exists public.stock_daily
    add column if not exists created_at timestamptz default now(),
    add column if not exists updated_at timestamptz default now();
alter table if exists public.raw_intraday
    add column if not exists fetched_at timestamptz default now();

-- ALTER on the partitioned parent propagates the column to existing partitions;
-- partitions created later inherit the complete parent row type.
alter table if exists public.stock_intraday
    add column if not exists created_at timestamptz default now(),
    add column if not exists updated_at timestamptz default now();

alter table if exists public.securities add column if not exists updated_at timestamptz default now();
alter table if exists public.indexes add column if not exists updated_at timestamptz default now();
alter table if exists public.index_components add column if not exists updated_at timestamptz default now();
alter table if exists public.foreign_trading add column if not exists updated_at timestamptz default now();
alter table if exists public.orderbook_snapshot
    add column if not exists created_at timestamptz default now(),
    add column if not exists updated_at timestamptz default now();

alter table if exists public.stream_raw_snapshot
    add column if not exists created_at timestamptz default now(),
    add column if not exists received_at timestamptz;
alter table if exists public.stream_quote_snapshot add column if not exists created_at timestamptz default now();
alter table if exists public.stream_trade_snapshot add column if not exists created_at timestamptz default now();
alter table if exists public.stream_foreign_snapshot add column if not exists created_at timestamptz default now();
alter table if exists public.stream_index_snapshot add column if not exists created_at timestamptz default now();
alter table if exists public.stream_status_snapshot add column if not exists created_at timestamptz default now();
alter table if exists public.stream_bar_snapshot add column if not exists created_at timestamptz default now();
alter table if exists public.features add column if not exists last_updated_at timestamptz default now();
alter table if exists public.data_quality_logs add column if not exists created_at timestamptz default now();

-- Defaults remain as compatibility fallbacks for legacy/manual writers. Main
-- TradingTPlus write paths always send application UTC timestamps.
-- No timestamp backfill is required or performed.

-- Verification (read-only):
-- select table_name, column_name, column_default
-- from information_schema.columns
-- where table_schema = 'public'
--   and column_name in ('created_at','updated_at','fetched_at','received_at','last_updated_at')
-- order by table_name, column_name;

-- Rollback guidance: leave additive columns in place. Removing stock_intraday.updated_at
-- would require coordinated code rollback and an explicit DROP on the partitioned parent.
