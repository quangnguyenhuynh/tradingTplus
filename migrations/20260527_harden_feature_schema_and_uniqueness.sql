-- Clean up and harden DB schema for TradingTPlus feature pipeline.
-- Idempotent where possible.

-- 1) Ensure features table has required columns for new pipeline.
alter table public.features
  add column if not exists open double precision,
  add column if not exists high double precision,
  add column if not exists low double precision,
  add column if not exists close double precision,
  add column if not exists volume bigint,
  add column if not exists value bigint,

  add column if not exists return_1m double precision,
  add column if not exists return_5m double precision,
  add column if not exists return_15m double precision,
  add column if not exists return_from_open double precision,
  add column if not exists return_from_prev_close double precision,

  add column if not exists ema9 double precision,
  add column if not exists ema20 double precision,
  add column if not exists ema50 double precision,
  add column if not exists ema9_above_ema20 boolean,
  add column if not exists ema20_above_ema50 boolean,

  add column if not exists rsi14 double precision,
  add column if not exists macd double precision,
  add column if not exists macd_signal double precision,
  add column if not exists macd_histogram double precision,

  add column if not exists volume_ma20 double precision,
  add column if not exists volume_ratio double precision,
  add column if not exists value_ma20 double precision,
  add column if not exists value_ratio double precision,

  add column if not exists high_20_bars double precision,
  add column if not exists low_20_bars double precision,
  add column if not exists close_above_high_20 boolean,
  add column if not exists close_below_low_20 boolean,

  add column if not exists vwap_intraday double precision,
  add column if not exists close_above_vwap boolean,
  add column if not exists distance_to_vwap_pct double precision,

  add column if not exists candle_range double precision,
  add column if not exists candle_body double precision,
  add column if not exists candle_body_pct double precision,
  add column if not exists close_position_in_candle double precision,

  add column if not exists last_updated_at timestamptz default now();

-- 2) Defensive type alignment for raw fields.
-- Convert volume/value from double precision to bigint only when safe.
do $$
declare
  volume_type text;
  value_type text;
  volume_has_special boolean;
  volume_has_non_integer boolean;
  value_has_special boolean;
  value_has_non_integer boolean;
begin
  select data_type into volume_type
  from information_schema.columns
  where table_schema = 'public' and table_name = 'features' and column_name = 'volume';

  if volume_type = 'double precision' then
    select exists (
      select 1
      from public.features
      where volume is not null
        and volume::text in ('Infinity', '-Infinity', 'NaN')
    ) into volume_has_special;

    if volume_has_special then
      raise exception 'Unsafe conversion: public.features.volume has Infinity/-Infinity/NaN; aborting bigint conversion.';
    end if;

    select exists (
      select 1
      from public.features
      where volume is not null
        and volume::text not in ('Infinity', '-Infinity', 'NaN')
        and volume <> trunc(volume)
    ) into volume_has_non_integer;

    if volume_has_non_integer then
      raise exception 'Unsafe conversion: public.features.volume has non-integer values; aborting bigint conversion.';
    end if;

    alter table public.features
      alter column volume type bigint using volume::bigint;
  end if;

  select data_type into value_type
  from information_schema.columns
  where table_schema = 'public' and table_name = 'features' and column_name = 'value';

  if value_type = 'double precision' then
    select exists (
      select 1
      from public.features
      where value is not null
        and value::text in ('Infinity', '-Infinity', 'NaN')
    ) into value_has_special;

    if value_has_special then
      raise exception 'Unsafe conversion: public.features.value has Infinity/-Infinity/NaN; aborting bigint conversion.';
    end if;

    select exists (
      select 1
      from public.features
      where value is not null
        and value::text not in ('Infinity', '-Infinity', 'NaN')
        and value <> trunc(value)
    ) into value_has_non_integer;

    if value_has_non_integer then
      raise exception 'Unsafe conversion: public.features.value has non-integer values; aborting bigint conversion.';
    end if;

    alter table public.features
      alter column value type bigint using value::bigint;
  end if;
end $$;

-- 3) Preserve legacy columns and annotate their status (idempotent with existence checks).
do $$
begin
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='rsi') then
    comment on column public.features.rsi is 'Legacy column. New feature pipeline uses rsi14.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='ema_20') then
    comment on column public.features.ema_20 is 'Legacy column. New feature pipeline uses ema20.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='ema_50') then
    comment on column public.features.ema_50 is 'Legacy column. New feature pipeline uses ema50.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='vwap') then
    comment on column public.features.vwap is 'Legacy column. New feature pipeline uses vwap_intraday.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='atr') then
    comment on column public.features.atr is 'Legacy column. Not currently written by new feature pipeline.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='volume_spike') then
    comment on column public.features.volume_spike is 'Legacy column. Not currently written by new feature pipeline.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='bb_upper') then
    comment on column public.features.bb_upper is 'Legacy column. Not currently written by new feature pipeline.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='bb_lower') then
    comment on column public.features.bb_lower is 'Legacy column. Not currently written by new feature pipeline.';
  end if;
end $$;

-- 4) Ensure features PK and indexes.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'features_pkey'
      and conrelid = 'public.features'::regclass
  ) then
    alter table public.features
      add constraint features_pkey primary key (symbol, timeframe, time);
  end if;
end $$;

create index if not exists idx_features_symbol_time
on public.features(symbol, timeframe, time desc);

-- 5) Remove old trading_signals uniqueness if present.
do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'trading_signals_symbol_signal_type_bucket_time_key'
      and conrelid = 'public.trading_signals'::regclass
  ) then
    alter table public.trading_signals
      drop constraint trading_signals_symbol_signal_type_bucket_time_key;
  end if;
end $$;

drop index if exists public.trading_signals_symbol_signal_type_bucket_time_uidx;

-- 6) Deduplicate orderbook_snapshot by keeping newest id per (symbol, time).
delete from public.orderbook_snapshot o
using public.orderbook_snapshot d
where o.symbol = d.symbol
  and o.time = d.time
  and o.id < d.id;

create unique index if not exists orderbook_snapshot_symbol_time_uidx
on public.orderbook_snapshot(symbol, time);

create index if not exists idx_orderbook_symbol_time
on public.orderbook_snapshot(symbol, time desc);

-- 7) Deduplicate trading_signals by keeping newest id per logical key.
delete from public.trading_signals o
using public.trading_signals d
where o.symbol is not distinct from d.symbol
  and o.timeframe is not distinct from d.timeframe
  and o.time is not distinct from d.time
  and o.signal_type is not distinct from d.signal_type
  and o.id < d.id;

create unique index if not exists trading_signals_symbol_timeframe_time_signal_type_uidx
on public.trading_signals(symbol, timeframe, time, signal_type);

create index if not exists idx_trading_signals_symbol_time
on public.trading_signals(symbol, timeframe, time desc);

-- NOTE:
-- - This migration does not modify stock_intraday partitions.
-- - This migration does not modify stock_intraday primary key.

-- Verification SQL (run manually):
-- 1) Verify features columns/types/defaults:
-- select column_name, data_type, is_nullable, column_default
-- from information_schema.columns
-- where table_schema = 'public' and table_name = 'features'
-- order by ordinal_position;

-- 2) Verify indexes/constraints:
-- select tablename, indexname, indexdef
-- from pg_indexes
-- where schemaname = 'public'
--   and tablename in ('features', 'orderbook_snapshot', 'trading_signals')
-- order by tablename, indexname;
--
-- select conname, pg_get_constraintdef(oid)
-- from pg_constraint
-- where conrelid in ('public.features'::regclass, 'public.trading_signals'::regclass)
-- order by conname;

-- 3) Verify no duplicate orderbook rows:
-- select symbol, time, count(*)
-- from public.orderbook_snapshot
-- group by symbol, time
-- having count(*) > 1;

-- 4) Verify no duplicate trading signal rows by logical key:
-- select symbol, timeframe, time, signal_type, count(*)
-- from public.trading_signals
-- group by symbol, timeframe, time, signal_type
-- having count(*) > 1;
