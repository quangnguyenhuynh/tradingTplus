-- Standardize SSI DailyIndex master/raw/clean storage.
-- Apply manually in Supabase SQL Editor during a maintenance window.
-- The rename is metadata-only; legacy raw migration scans index_daily once.

do $$
begin
  if to_regclass('public.indexes') is not null and to_regclass('public.index_master') is not null then
    raise exception 'Ambiguous index master state: both public.indexes and public.index_master exist';
  elsif to_regclass('public.indexes') is not null then
    alter table public.indexes rename to index_master;
  elsif to_regclass('public.index_master') is null then
    raise exception 'Missing public.indexes/public.index_master; apply the base SSI ingest schema first';
  end if;
end $$;

do $$ begin
  if exists (select 1 from pg_constraint where conname='indexes_pkey' and conrelid='public.index_master'::regclass) then
    alter table public.index_master rename constraint indexes_pkey to index_master_pkey;
  end if;
end $$;

create table if not exists public.index_raw_daily (
  index_code text not null,
  trading_date date not null,
  data_hash text not null,
  payload jsonb not null,
  source text not null default 'SSI_DailyIndex',
  fetched_at timestamptz null,
  created_at timestamptz not null
);
create unique index if not exists index_raw_daily_identity_uidx
  on public.index_raw_daily(index_code,trading_date,data_hash);

-- Fetch time is intentionally NULL because index_daily.raw did not preserve it.
insert into public.index_raw_daily(index_code,trading_date,data_hash,payload,source,fetched_at,created_at)
select d.index_code, d.trading_date,
       encode(digest(d.raw::text,'sha256'),'hex'), d.raw,
       'SSI_DailyIndex_legacy', null, statement_timestamp()
from public.index_daily d
where d.raw is not null and jsonb_typeof(d.raw)='object'
on conflict (index_code,trading_date,data_hash) do nothing;

create unique index if not exists index_daily_index_code_trading_date_uidx
  on public.index_daily(index_code,trading_date);

-- There is now one canonical raw contract. The preceding INSERT must complete
-- successfully before this transactional migration can reach the DROP.
alter table public.index_daily drop column if exists raw;

comment on table public.index_master is 'Canonical SSI index definitions synchronized from IndexList.';
comment on table public.index_raw_daily is 'Immutable semantic SSI DailyIndex payload evidence; fetched_at is NULL when unavailable.';
comment on table public.index_daily is 'Validated normalized SSI DailyIndex rows; canonical raw payloads live in index_raw_daily.';

alter table public.index_master enable row level security;
alter table public.index_raw_daily enable row level security;
alter table public.index_daily enable row level security;
revoke all on table public.index_master,index_raw_daily,index_daily from anon,authenticated;
grant all on table public.index_master,index_raw_daily,index_daily to service_role;

-- Verification (run after COMMIT):
-- select to_regclass('public.index_master'),to_regclass('public.index_raw_daily'),to_regclass('public.index_daily');
-- select count(*) master_rows from public.index_master;
-- select source,count(*) from public.index_raw_daily group by source order by source;
-- select count(*) from public.index_raw_daily where index_code is null or trading_date is null or payload is null;
-- select index_code,trading_date,data_hash,count(*) from public.index_raw_daily group by 1,2,3 having count(*)>1;
-- select index_code,trading_date,count(*) from public.index_daily group by 1,2 having count(*)>1;
-- select indexname,indexdef from pg_indexes where schemaname='public' and tablename in ('index_master','index_raw_daily','index_daily');
-- select d.index_code from public.index_daily d left join public.index_master m using(index_code) where m.index_code is null group by d.index_code;
-- select d.index_code,d.trading_date,r.source,r.data_hash from public.index_daily d left join public.index_raw_daily r using(index_code,trading_date) order by d.trading_date desc limit 20;
-- Compare `select count(*) from public.indexes` before migration with index_master after migration.

-- Rollback guidance: stop writers; add index_daily.raw jsonb; restore one chosen
-- payload per clean key from index_raw_daily; drop index_raw_daily; rename
-- index_master back to indexes. Do not roll back if new raw-only rejected payloads
-- have not first been exported, because doing so would discard validation evidence.
