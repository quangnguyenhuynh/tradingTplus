-- Align orderbook_snapshot with SSI streaming quote payload naming.
-- Idempotent: adds raw/created_at and bid_vol/ask_vol columns without dropping legacy columns.

alter table if exists public.orderbook_snapshot
  add column if not exists raw jsonb,
  add column if not exists created_at timestamptz default now();

alter table if exists public.orderbook_snapshot
  add column if not exists bid_vol_1 numeric,
  add column if not exists ask_vol_1 numeric,
  add column if not exists bid_vol_2 numeric,
  add column if not exists ask_vol_2 numeric,
  add column if not exists bid_vol_3 numeric,
  add column if not exists ask_vol_3 numeric,
  add column if not exists bid_vol_4 numeric,
  add column if not exists ask_vol_4 numeric,
  add column if not exists bid_vol_5 numeric,
  add column if not exists ask_vol_5 numeric,
  add column if not exists bid_vol_6 numeric,
  add column if not exists ask_vol_6 numeric,
  add column if not exists bid_vol_7 numeric,
  add column if not exists ask_vol_7 numeric,
  add column if not exists bid_vol_8 numeric,
  add column if not exists ask_vol_8 numeric,
  add column if not exists bid_vol_9 numeric,
  add column if not exists ask_vol_9 numeric,
  add column if not exists bid_vol_10 numeric,
  add column if not exists ask_vol_10 numeric;

create unique index if not exists orderbook_snapshot_symbol_time_uidx
on public.orderbook_snapshot(symbol, time);
