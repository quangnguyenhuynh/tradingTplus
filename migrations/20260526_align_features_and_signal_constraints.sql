-- Align feature-engine schema and trading-signal uniqueness with current code.
-- This migration is intentionally additive/compatible to preserve existing data.

-- 1) Keep PK on features as (symbol, timeframe, time).
--    Add only if missing; do not replace existing PK if already correct.
do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'features_pkey'
      and conrelid = 'public.features'::regclass
  ) then
    alter table public.features
      add constraint features_pkey primary key (symbol, timeframe, time);
  end if;
end $$;

-- 2) Safe column renames for compatibility with feature engine naming.
--    We only rename when old column exists and new column does not.
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'features' and column_name = 'ema_20'
  ) and not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'features' and column_name = 'ema20'
  ) then
    alter table public.features rename column ema_20 to ema20;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'features' and column_name = 'ema_50'
  ) and not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'features' and column_name = 'ema50'
  ) then
    alter table public.features rename column ema_50 to ema50;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'features' and column_name = 'vwap'
  ) and not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'features' and column_name = 'vwap_intraday'
  ) then
    alter table public.features rename column vwap to vwap_intraday;
  end if;
end $$;

-- 3) Add missing columns required by feature engine.
--    Numeric indicators are double precision; flags are boolean.
alter table public.features
  add column if not exists open double precision,
  add column if not exists high double precision,
  add column if not exists low double precision,
  add column if not exists close double precision,
  add column if not exists volume double precision,
  add column if not exists value double precision,

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

  -- Do not auto-rename legacy `rsi` to `rsi14`; keep both unless manually validated.
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

  add column if not exists last_updated_at timestamptz;

-- 4) Ensure lookup/perf index for feature reads by symbol+timeframe+latest time.
create index if not exists idx_features_symbol_time
on public.features(symbol, timeframe, time desc);

-- 5) Replace legacy trading_signals uniqueness.
--    Drop old unique constraint/index on (symbol, signal_type, bucket_time).
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

--    Add new uniqueness that matches current upsert identity.
create unique index if not exists trading_signals_symbol_timeframe_time_signal_type_uidx
on public.trading_signals(symbol, timeframe, time, signal_type);

-- 6) Add read/perf index for trading_signals by symbol+timeframe+latest time.
create index if not exists idx_trading_signals_symbol_time
on public.trading_signals(symbol, timeframe, time desc);

-- NOTE: This migration does not touch stock_intraday partitions.
