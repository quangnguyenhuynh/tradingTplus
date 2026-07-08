-- Fix orderbook snapshot column names to match application/schema contract.
-- SSI quote messages use BidVol/AskVol; DB columns should be bid_vol_N/ask_vol_N.

alter table if exists public.orderbook_snapshot
  add column if not exists raw jsonb,
  add column if not exists created_at timestamptz default now();

alter table if exists public.orderbook_snapshot
  add column if not exists bid_price_1 numeric,
  add column if not exists bid_vol_1 numeric,
  add column if not exists ask_price_1 numeric,
  add column if not exists ask_vol_1 numeric,
  add column if not exists bid_price_2 numeric,
  add column if not exists bid_vol_2 numeric,
  add column if not exists ask_price_2 numeric,
  add column if not exists ask_vol_2 numeric,
  add column if not exists bid_price_3 numeric,
  add column if not exists bid_vol_3 numeric,
  add column if not exists ask_price_3 numeric,
  add column if not exists ask_vol_3 numeric,
  add column if not exists bid_price_4 numeric,
  add column if not exists bid_vol_4 numeric,
  add column if not exists ask_price_4 numeric,
  add column if not exists ask_vol_4 numeric,
  add column if not exists bid_price_5 numeric,
  add column if not exists bid_vol_5 numeric,
  add column if not exists ask_price_5 numeric,
  add column if not exists ask_vol_5 numeric,
  add column if not exists bid_price_6 numeric,
  add column if not exists bid_vol_6 numeric,
  add column if not exists ask_price_6 numeric,
  add column if not exists ask_vol_6 numeric,
  add column if not exists bid_price_7 numeric,
  add column if not exists bid_vol_7 numeric,
  add column if not exists ask_price_7 numeric,
  add column if not exists ask_vol_7 numeric,
  add column if not exists bid_price_8 numeric,
  add column if not exists bid_vol_8 numeric,
  add column if not exists ask_price_8 numeric,
  add column if not exists ask_vol_8 numeric,
  add column if not exists bid_price_9 numeric,
  add column if not exists bid_vol_9 numeric,
  add column if not exists ask_price_9 numeric,
  add column if not exists ask_vol_9 numeric,
  add column if not exists bid_price_10 numeric,
  add column if not exists bid_vol_10 numeric,
  add column if not exists ask_price_10 numeric,
  add column if not exists ask_vol_10 numeric;

create unique index if not exists orderbook_snapshot_symbol_time_uidx
on public.orderbook_snapshot(symbol, time);
