-- Rebuild index_daily for the verified SSI v3 indexSummary clean contract.
-- Apply manually during a maintenance window. This intentionally removes the
-- untrusted SSI v2 clean history; index_raw_daily evidence is never modified.
begin;

lock table public.index_daily in access exclusive mode;

-- Fail rather than cascading through an unknown dependent object. Operators
-- must review/drop/recreate such dependencies explicitly before retrying.
do $$
begin
  if to_regclass('public.index_daily') is null then
    raise exception 'Missing public.index_daily; apply prior index migrations first';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.index_daily'::regclass
      and contype = 'p'
      and conname = 'index_daily_pkey'
  ) then
    raise exception 'Missing index_daily_pkey; apply 20260826_add_index_daily_primary_key.sql first';
  end if;
end $$;

-- No SSI v2 clean value is promoted into the v3 semantic contract. In
-- particular, change is never copied to index_change. Raw v2 evidence remains.
delete from public.index_daily;

alter table public.index_daily
  drop column if exists change,
  drop column if exists ratio_change,
  drop column if exists total_trade,
  drop column if exists total_match_vol,
  drop column if exists total_match_val,
  drop column if exists total_deal_vol,
  drop column if exists total_deal_val,
  drop column if exists total_vol,
  drop column if exists total_val,
  drop column if exists type_index,
  drop column if exists index_name,
  drop column if exists advances,
  drop column if exists no_changes,
  drop column if exists declines,
  drop column if exists ceilings,
  drop column if exists floors,
  drop column if exists trading_session,
  drop column if exists market,
  drop column if exists exchange,
  add column if not exists index_change numeric,
  add column if not exists index_change_percentage numeric,
  add column if not exists total_trade_volume numeric,
  add column if not exists total_trade_value numeric,
  add column if not exists total_match_volume numeric,
  add column if not exists total_match_value numeric,
  add column if not exists total_deal_volume numeric,
  add column if not exists total_deal_value numeric,
  add column if not exists total_advance_stock numeric,
  add column if not exists total_ceiling_stock numeric,
  add column if not exists total_decline_stock numeric,
  add column if not exists total_floor_stock numeric,
  add column if not exists total_no_change_stock numeric,
  add column if not exists total_prop_buy_volume numeric,
  add column if not exists total_prop_buy_value numeric,
  add column if not exists total_prop_sell_volume numeric,
  add column if not exists total_prop_sell_value numeric,
  add column if not exists total_foreign_buy_volume numeric,
  add column if not exists total_foreign_buy_value numeric,
  add column if not exists total_foreign_sell_volume numeric,
  add column if not exists total_foreign_sell_value numeric,
  add column if not exists net_foreign_purchase_volume numeric,
  add column if not exists net_foreign_purchase_value numeric;

comment on table public.index_daily is
  'Validated SSI v3 indexSummary rows (contract 2.0.0); raw payloads live in index_raw_daily.';
comment on column public.index_daily.index_change is 'SSI v3 indexChange in index points; no ingest scaling.';
comment on column public.index_daily.index_change_percentage is 'SSI v3 indexChangePercentage in provider percent units; no ingest scaling.';

commit;

-- Verification (after COMMIT):
-- select column_name,data_type,is_nullable from information_schema.columns
-- where table_schema='public' and table_name='index_daily' order by ordinal_position;
-- select conname,pg_get_constraintdef(oid) from pg_constraint
-- where conrelid='public.index_daily'::regclass and contype='p';
-- select count(*) from public.index_daily; -- expected 0 before SSI v3 backfill
-- select source,count(*) from public.index_raw_daily group by source order by source;
-- Verify that legacy columns are absent using information_schema.columns.
-- Backfill clean rows from SSI v3, validate them, then rerun index features separately.

-- Rollback guidance: restore the previous clean columns from the prior migration
-- definition only. Do not reconstruct them from the new v3 columns, and never
-- delete index_raw_daily. A rollback requires a separate v2 clean rebuild decision.
