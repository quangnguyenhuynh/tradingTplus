-- Ensure orderbook upsert(on_conflict='symbol,time') is backed by a unique constraint/index.
-- This hardens data integrity for T+ ingestion and prevents silent duplicate divergence.

create unique index if not exists orderbook_snapshot_symbol_time_uidx
on public.orderbook_snapshot(symbol, time);
