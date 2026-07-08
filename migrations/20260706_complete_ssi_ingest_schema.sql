-- Complete SSI ingest schema for securities, stock daily, and index daily data.
-- Idempotent migration; preserves legacy symbols table for compatibility.

create table if not exists public.securities (
  symbol text primary key,
  market text,
  stock_name text,
  stock_en_name text,
  sec_type text,
  exchange text,
  issuer text,
  lot_size numeric,
  issue_date date,
  maturity_date date,
  first_trading_date date,
  last_trading_date date,
  listed_share numeric,
  tick_price1 numeric,
  tick_increment1 numeric,
  tick_price2 numeric,
  tick_increment2 numeric,
  tick_price3 numeric,
  tick_increment3 numeric,
  tick_price4 numeric,
  tick_increment4 numeric,
  raw jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.stock_daily (
  symbol text not null,
  trading_date date not null,
  price_change numeric,
  per_price_change numeric,
  ceiling_price numeric,
  floor_price numeric,
  ref_price numeric,
  open_price numeric,
  highest_price numeric,
  lowest_price numeric,
  close_price numeric,
  average_price numeric,
  close_price_adjusted numeric,
  total_match_vol numeric,
  total_match_val numeric,
  total_deal_vol numeric,
  total_deal_val numeric,
  total_traded_vol numeric,
  total_traded_value numeric,
  foreign_buy_vol_total numeric,
  foreign_sell_vol_total numeric,
  foreign_buy_val_total numeric,
  foreign_sell_val_total numeric,
  foreign_current_room numeric,
  net_foreign_vol numeric,
  net_foreign_val numeric,
  total_buy_trade numeric,
  total_buy_trade_vol numeric,
  total_sell_trade numeric,
  total_sell_trade_vol numeric,
  raw jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create unique index if not exists stock_daily_symbol_trading_date_uidx on public.stock_daily(symbol, trading_date);

create table if not exists public.index_daily (
  index_code text not null,
  trading_date date not null,
  index_value numeric,
  change numeric,
  ratio_change numeric,
  total_trade numeric,
  total_match_vol numeric,
  total_match_val numeric,
  total_deal_vol numeric,
  total_deal_val numeric,
  total_vol numeric,
  total_val numeric,
  type_index text,
  index_name text,
  advances numeric,
  no_changes numeric,
  declines numeric,
  ceilings numeric,
  floors numeric,
  trading_session text,
  market text,
  exchange text,
  raw jsonb
);
create unique index if not exists index_daily_index_code_trading_date_uidx on public.index_daily(index_code, trading_date);

create table if not exists public.indexes (
  index_code text primary key,
  index_name text,
  exchange text,
  raw jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.index_components (
  index_code text not null,
  symbol text not null,
  exchange text,
  raw jsonb,
  updated_at timestamptz default now()
);
create unique index if not exists index_components_index_code_symbol_uidx on public.index_components(index_code, symbol);

create table if not exists public.raw_daily (
  symbol text not null,
  trading_date date not null,
  data_hash text not null,
  payload jsonb,
  created_at timestamptz default now()
);
create unique index if not exists raw_daily_symbol_trading_date_data_hash_uidx on public.raw_daily(symbol, trading_date, data_hash);
