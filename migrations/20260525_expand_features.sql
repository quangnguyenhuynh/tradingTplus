-- Expand features schema to match src/engine/feature_engine.py FEATURE_COLUMNS
-- Safe to run multiple times.

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

create unique index if not exists features_symbol_timeframe_time_uidx
on public.features(symbol, timeframe, time);
