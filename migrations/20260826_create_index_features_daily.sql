-- Dedicated Index Daily Feature V1 storage. Apply manually after the standardized
-- index pipeline migration. This does not alter public.features or stock data.
create table if not exists public.index_features_daily (
  index_code text not null,
  trading_date date not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  index_value numeric,
  total_vol numeric,
  total_val numeric,
  breadth_total numeric,
  index_return_1d double precision,
  index_return_3d double precision,
  index_return_5d double precision,
  index_return_10d double precision,
  index_ma20 double precision,
  index_ma50 double precision,
  index_distance_ma20 double precision,
  index_distance_ma50 double precision,
  index_rsi14 double precision,
  index_macd double precision,
  index_macd_signal double precision,
  index_macd_histogram double precision,
  index_volatility_20d double precision,
  index_drawdown_20d double precision,
  index_drawdown_60d double precision,
  index_breadth_net double precision,
  index_breadth_ratio double precision,
  index_advance_pct double precision,
  index_decline_pct double precision,
  index_unchanged_pct double precision,
  index_ceiling_pct double precision,
  index_floor_pct double precision,
  index_limit_balance double precision,
  index_breadth_ma5 double precision,
  index_breadth_ma10 double precision,
  index_total_vol_ma20 double precision,
  index_total_vol_ratio20 double precision,
  index_total_val_ma20 double precision,
  index_total_val_ratio20 double precision,
  index_match_vol_ratio double precision,
  index_match_val_ratio double precision,
  index_deal_vol_ratio double precision,
  index_deal_val_ratio double precision,
  constraint index_features_daily_pkey primary key (index_code, trading_date),
  constraint index_features_daily_index_code_fkey foreign key (index_code)
    references public.index_master(index_code)
);

comment on table public.index_features_daily is
  'Deterministic daily market-index features calculated only from public.index_daily.';
comment on column public.index_features_daily.breadth_total is
  'advances + no_changes + declines; NULL unless all three clean source values exist.';

alter table public.index_features_daily enable row level security;
revoke all on table public.index_features_daily from anon, authenticated;
grant all on table public.index_features_daily to service_role;

-- Verification (read-only, after COMMIT):
-- select to_regclass('public.index_features_daily');
-- select conname,contype from pg_constraint where conrelid='public.index_features_daily'::regclass;
-- select relrowsecurity from pg_class where oid='public.index_features_daily'::regclass;
-- select has_table_privilege('anon','public.index_features_daily','select'),
--        has_table_privilege('authenticated','public.index_features_daily','select'),
--        has_table_privilege('service_role','public.index_features_daily','insert');
-- select index_code,trading_date,count(*) from public.index_features_daily group by 1,2 having count(*)>1;

-- Rollback: stop the index-feature writer, export rows if needed, then run:
-- drop table if exists public.index_features_daily;
