-- Promote the existing index_daily natural-key unique index to the table PK.
-- Apply manually in Supabase SQL Editor during a maintenance window.
-- No rows are deleted, rewritten, deduplicated, or backfilled.

begin;

do $$
declare
  null_key_count bigint;
  duplicate_group_count bigint;
  existing_primary_key text;
begin
  if to_regclass('public.index_daily') is null then
    raise exception 'Missing public.index_daily; apply the SSI ingest schema first';
  end if;

  select c.conname
    into existing_primary_key
  from pg_constraint c
  where c.conrelid = 'public.index_daily'::regclass
    and c.contype = 'p';

  if existing_primary_key is not null then
    raise exception 'public.index_daily already has primary key constraint %', existing_primary_key;
  end if;

  select count(*)
    into null_key_count
  from public.index_daily
  where index_code is null
     or trading_date is null;

  if null_key_count > 0 then
    raise exception 'Cannot add index_daily_pkey: % row(s) have NULL index_code or trading_date', null_key_count;
  end if;

  select count(*)
    into duplicate_group_count
  from (
    select index_code, trading_date
    from public.index_daily
    group by index_code, trading_date
    having count(*) > 1
  ) duplicate_keys;

  if duplicate_group_count > 0 then
    raise exception 'Cannot add index_daily_pkey: % duplicate (index_code, trading_date) group(s) exist', duplicate_group_count;
  end if;

  if to_regclass('public.index_daily_index_code_trading_date_uidx') is null then
    raise exception 'Missing index_daily_index_code_trading_date_uidx; apply the current index_daily schema migrations first';
  end if;
end $$;

alter table public.index_daily
  alter column index_code set not null,
  alter column trading_date set not null;

-- Reuse the existing unique index so the primary key does not add a redundant
-- second btree. PostgreSQL associates/renames that index to index_daily_pkey.
alter table public.index_daily
  add constraint index_daily_pkey primary key
  using index index_daily_index_code_trading_date_uidx;

commit;

-- Verification (run after COMMIT):
-- select c.conname, array_agg(a.attname order by key_column.ordinality) as key_columns
-- from pg_constraint c
-- cross join lateral unnest(c.conkey) with ordinality as key_column(attnum, ordinality)
-- join pg_attribute a on a.attrelid = c.conrelid and a.attnum = key_column.attnum
-- where c.conrelid = 'public.index_daily'::regclass and c.contype = 'p'
-- group by c.conname;
-- select column_name,is_nullable from information_schema.columns
-- where table_schema='public' and table_name='index_daily'
--   and column_name in ('index_code','trading_date') order by ordinal_position;
-- select index_code,trading_date,count(*) from public.index_daily group by 1,2 having count(*)>1;

-- Rollback guidance (metadata only; do not run during normal deployment):
-- begin;
-- alter table public.index_daily drop constraint if exists index_daily_pkey;
-- create unique index if not exists index_daily_index_code_trading_date_uidx
--   on public.index_daily(index_code,trading_date);
-- commit;
