-- Make application payloads the sole source of pipeline audit timestamps.
-- This migration is idempotent and does not update or delete historical rows.

-- ALTER on the partitioned parent propagates the column to existing partitions;
-- partitions created later inherit the parent row type.
alter table if exists public.stock_intraday
    add column if not exists updated_at timestamptz;

-- Drop defaults only for the explicitly scoped audit columns that exist. The
-- catalog-driven form tolerates deployments where an optional snapshot table
-- has not yet been created.
do $$
declare
    audit_column record;
begin
    for audit_column in
        select table_name, column_name
        from information_schema.columns
        where table_schema = 'public'
          and (table_name, column_name) in (
              ('raw_daily', 'created_at'),
              ('stock_daily', 'created_at'),
              ('stock_daily', 'updated_at'),
              ('raw_intraday', 'fetched_at'),
              ('stock_intraday', 'created_at'),
              ('stock_intraday', 'updated_at'),
              ('securities', 'updated_at'),
              ('indexes', 'updated_at'),
              ('index_components', 'updated_at'),
              ('stream_raw_snapshot', 'received_at'),
              ('stream_raw_snapshot', 'created_at'),
              ('stream_quote_snapshot', 'created_at'),
              ('stream_trade_snapshot', 'created_at'),
              ('stream_foreign_snapshot', 'created_at'),
              ('stream_index_snapshot', 'created_at'),
              ('stream_status_snapshot', 'created_at'),
              ('stream_bar_snapshot', 'created_at'),
              ('features', 'last_updated_at')
          )
    loop
        execute format(
            'alter table public.%I alter column %I drop default',
            audit_column.table_name,
            audit_column.column_name
        );
    end loop;
end
$$;

-- Verification (read-only; expected column_default is NULL):
-- select table_name, column_name, column_default
-- from information_schema.columns
-- where table_schema = 'public'
--   and column_name in
--       ('created_at', 'updated_at', 'fetched_at', 'received_at', 'last_updated_at')
-- order by table_name, column_name;

-- Rollback guidance: application writers remain compatible without defaults.
-- If an external legacy writer requires defaults, restore them only after a
-- separate compatibility review; no data rollback or timestamp backfill is needed.
