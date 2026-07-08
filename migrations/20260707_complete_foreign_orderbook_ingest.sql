-- Complete daily foreign trading and orderbook ingest compatibility.
-- Idempotent/additive: keeps existing tables and adds required research/debug columns.

-- Ensure tables exist on fresh/dev environments.
create table if not exists public.foreign_trading (
  symbol text not null,
  trading_date date,
  time timestamptz,
  foreign_buy_vol numeric,
  foreign_sell_vol numeric,
  foreign_buy_val numeric,
  foreign_sell_val numeric,
  net_foreign_vol numeric,
  net_foreign_val numeric,
  foreign_room numeric,
  foreign_current_room numeric,
  buy_vol numeric,
  sell_vol numeric,
  net_vol numeric,
  raw jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.orderbook_snapshot (
  symbol text not null,
  time timestamptz not null,
  total_bid_depth_10 numeric,
  total_ask_depth_10 numeric,
  orderbook_imbalance numeric,
  pressure_score numeric,
  raw jsonb,
  updated_at timestamptz default now()
);

alter table if exists public.foreign_trading
  add column if not exists trading_date date,
  add column if not exists foreign_buy_vol numeric,
  add column if not exists foreign_sell_vol numeric,
  add column if not exists foreign_buy_val numeric,
  add column if not exists foreign_sell_val numeric,
  add column if not exists net_foreign_vol numeric,
  add column if not exists net_foreign_val numeric,
  add column if not exists foreign_room numeric,
  add column if not exists foreign_current_room numeric,
  add column if not exists raw jsonb,
  add column if not exists updated_at timestamptz default now();

-- Backward-compatible aliases for older code/query names.
alter table if exists public.foreign_trading
  add column if not exists buy_vol numeric,
  add column if not exists sell_vol numeric,
  add column if not exists net_vol numeric;

create unique index if not exists foreign_trading_symbol_trading_date_uidx
on public.foreign_trading(symbol, trading_date);

alter table if exists public.orderbook_snapshot
  add column if not exists raw jsonb,
  add column if not exists updated_at timestamptz default now();

-- Ensure 10-level depth columns exist for bid/ask snapshots.
alter table if exists public.orderbook_snapshot
  add column if not exists bid_price_1 numeric,
  add column if not exists bid_volume_1 numeric,
  add column if not exists ask_price_1 numeric,
  add column if not exists ask_volume_1 numeric,
  add column if not exists bid_price_2 numeric,
  add column if not exists bid_volume_2 numeric,
  add column if not exists ask_price_2 numeric,
  add column if not exists ask_volume_2 numeric,
  add column if not exists bid_price_3 numeric,
  add column if not exists bid_volume_3 numeric,
  add column if not exists ask_price_3 numeric,
  add column if not exists ask_volume_3 numeric,
  add column if not exists bid_price_4 numeric,
  add column if not exists bid_volume_4 numeric,
  add column if not exists ask_price_4 numeric,
  add column if not exists ask_volume_4 numeric,
  add column if not exists bid_price_5 numeric,
  add column if not exists bid_volume_5 numeric,
  add column if not exists ask_price_5 numeric,
  add column if not exists ask_volume_5 numeric,
  add column if not exists bid_price_6 numeric,
  add column if not exists bid_volume_6 numeric,
  add column if not exists ask_price_6 numeric,
  add column if not exists ask_volume_6 numeric,
  add column if not exists bid_price_7 numeric,
  add column if not exists bid_volume_7 numeric,
  add column if not exists ask_price_7 numeric,
  add column if not exists ask_volume_7 numeric,
  add column if not exists bid_price_8 numeric,
  add column if not exists bid_volume_8 numeric,
  add column if not exists ask_price_8 numeric,
  add column if not exists ask_volume_8 numeric,
  add column if not exists bid_price_9 numeric,
  add column if not exists bid_volume_9 numeric,
  add column if not exists ask_price_9 numeric,
  add column if not exists ask_volume_9 numeric,
  add column if not exists bid_price_10 numeric,
  add column if not exists bid_volume_10 numeric,
  add column if not exists ask_price_10 numeric,
  add column if not exists ask_volume_10 numeric;

create unique index if not exists orderbook_snapshot_symbol_time_uidx
on public.orderbook_snapshot(symbol, time);
