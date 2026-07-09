-- Align public.features with TradingTPlus phase 1 feature contract.
-- Phase 1 features are derived only from stock_intraday 1m OHLCV/value and
-- stock_daily previous-close context. This migration is intentionally
-- idempotent and does not drop legacy columns yet.

alter table public.features
  add column if not exists symbol text,
  add column if not exists timeframe text,
  add column if not exists time timestamptz,
  add column if not exists last_updated_at timestamptz default now(),
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
  add column if not exists close_position_in_candle double precision;

-- Tighten required phase 1 keys for new writes. Existing migrations already
-- create these as not null in normal deployments; this keeps the contract clear.
alter table public.features
  alter column symbol set not null,
  alter column timeframe set not null,
  alter column time set not null;

create unique index if not exists features_symbol_timeframe_time_uidx
on public.features(symbol, timeframe, time);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'features_symbol_timeframe_time_key'
      and conrelid = 'public.features'::regclass
  ) then
    alter table public.features
      add constraint features_symbol_timeframe_time_key unique using index features_symbol_timeframe_time_uidx;
  end if;
exception
  when duplicate_object then null;
  when others then
    -- If the index is already owned by another constraint (for example a PK),
    -- the unique index itself is sufficient for Supabase upsert on_conflict.
    if sqlstate <> '42809' then
      raise;
    end if;
end $$;

do $$
begin
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='rsi') then
    comment on column public.features.rsi is 'Deprecated legacy phase 0 column. Phase 1 uses rsi14.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='atr') then
    comment on column public.features.atr is 'Deprecated legacy phase 0 column. Phase 1 does not compute ATR.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='ema_20') then
    comment on column public.features.ema_20 is 'Deprecated legacy phase 0 column. Phase 1 uses ema20.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='ema_50') then
    comment on column public.features.ema_50 is 'Deprecated legacy phase 0 column. Phase 1 uses ema50.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='vwap') then
    comment on column public.features.vwap is 'Deprecated legacy phase 0 column. Phase 1 uses vwap_intraday.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='bb_upper') then
    comment on column public.features.bb_upper is 'Deprecated legacy phase 0 column. Phase 1 does not compute Bollinger Bands.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='bb_lower') then
    comment on column public.features.bb_lower is 'Deprecated legacy phase 0 column. Phase 1 does not compute Bollinger Bands.';
  end if;
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='features' and column_name='volume_spike') then
    comment on column public.features.volume_spike is 'Deprecated legacy phase 0 column. Phase 1 uses volume_ratio.';
  end if;
end $$;
