-- Stock Screener V1 results (manual deployment; no existing data changed).
create table if not exists public.stock_screener_results (
    symbol text not null references public.symbols(symbol),
    trading_date date not null,
    screener_version text not null,
    status text not null check (status in ('PASS', 'FAIL', 'NOT_EVALUABLE')),
    score smallint,
    rule_results jsonb not null,
    missing_fields text[] not null default '{}',
    source_feature_time timestamptz,
    source_feature_updated_at timestamptz,
    evaluated_at timestamptz not null,
    primary key (symbol, trading_date, screener_version),
    constraint stock_screener_score_check check (
      (status = 'NOT_EVALUABLE' and score is null)
      or (status in ('PASS', 'FAIL') and score between 0 and 100)
    )
);
create index if not exists stock_screener_results_date_idx
on public.stock_screener_results (trading_date desc, screener_version, status);
alter table public.stock_screener_results enable row level security;
-- No anon/authenticated policies: service-role backend only.
comment on table public.stock_screener_results is
  'Versioned research-only EOD screener; score is satisfied-gate count, not a probability.';

-- Verify after manual deployment:
-- select column_name, data_type from information_schema.columns
--  where table_schema='public' and table_name='stock_screener_results'
--  order by ordinal_position;
-- select relrowsecurity from pg_class where oid='public.stock_screener_results'::regclass;
-- select conname from pg_constraint where conrelid='public.stock_screener_results'::regclass;
-- Deployment: additive CREATE TABLE / index; metadata locks only on this new table.
-- Data: no writes to stock_features, stock_daily or existing screener rows.
-- Backfill: optional, separate operator-triggered exact-date CLI runs.
-- Rollback (only if no rows need preservation):
-- drop table if exists public.stock_screener_results;
