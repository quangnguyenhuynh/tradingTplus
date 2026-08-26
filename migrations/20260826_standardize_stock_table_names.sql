-- Standardize stock-only table names. Apply manually during a maintenance window
-- with all scheduled writers paused. Renames are metadata-only but take brief
-- ACCESS EXCLUSIVE locks. No rows are copied, rewritten, or removed.
begin;
set local lock_timeout = '5s';

create temporary table stock_table_rename_map(old_name text primary key, new_name text unique) on commit drop;
insert into stock_table_rename_map(old_name,new_name) values
 ('raw_daily','stock_raw_daily'),
 ('raw_intraday','stock_raw_intraday'),
 ('features','stock_features'),
 ('foreign_trading','stock_foreign_trading'),
 ('orderbook_snapshot','stock_orderbook_snapshot'),
 ('data_quality_logs','stock_data_quality_logs');

do $migration$
declare item record; old_oid oid; new_oid oid;
begin
  for item in select * from stock_table_rename_map order by old_name loop
    old_oid := to_regclass(format('public.%I',item.old_name));
    new_oid := to_regclass(format('public.%I',item.new_name));
    if old_oid is not null and new_oid is not null then
      raise exception 'ambiguous stock table rename: both public.% and public.% exist',item.old_name,item.new_name;
    elsif old_oid is null and new_oid is null then
      raise exception 'missing stock schema: neither public.% nor public.% exists',item.old_name,item.new_name;
    elsif old_oid is not null then
      execute format('alter table public.%I rename to %I',item.old_name,item.new_name);
    end if;
  end loop;
end $migration$;

-- Rename attached constraints, their backing indexes (where PostgreSQL has not
-- already done so), ordinary indexes, and table-owned sequences. A pre-existing
-- target name is treated as a collision and left untouched; object identity and
-- dependencies are never changed.
do $objects$
declare m record; obj record; proposed text;
begin
  for m in select * from stock_table_rename_map order by old_name loop
    for obj in
      select c.oid,c.conname from pg_constraint c
      where c.conrelid=format('public.%I',m.new_name)::regclass and strpos(c.conname,m.old_name)>0
    loop
      proposed:=replace(obj.conname,m.old_name,m.new_name);
      if not exists(select 1 from pg_constraint where connamespace='public'::regnamespace and conname=proposed) then
        execute format('alter table public.%I rename constraint %I to %I',m.new_name,obj.conname,proposed);
      end if;
    end loop;
    for obj in
      select i.indexrelid,c.relname from pg_index i join pg_class c on c.oid=i.indexrelid
      where i.indrelid=format('public.%I',m.new_name)::regclass and strpos(c.relname,m.old_name)>0
    loop
      proposed:=replace(obj.relname,m.old_name,m.new_name);
      if to_regclass(format('public.%I',proposed)) is null then
        execute format('alter index public.%I rename to %I',obj.relname,proposed);
      end if;
    end loop;
    for obj in
      select seq.oid,seq.relname from pg_class seq
      join pg_depend d on d.objid=seq.oid and d.deptype='a'
      where seq.relkind='S' and d.refobjid=format('public.%I',m.new_name)::regclass
        and strpos(seq.relname,m.old_name)>0
    loop
      proposed:=replace(obj.relname,m.old_name,m.new_name);
      if to_regclass(format('public.%I',proposed)) is null then
        execute format('alter sequence public.%I rename to %I',obj.relname,proposed);
      end if;
    end loop;
  end loop;
end $objects$;

create or replace function public.cleanup_old_orderbook(days integer default 14) returns void
language plpgsql as $$ begin
  delete from public.stock_orderbook_snapshot where time < now()-(days||' days')::interval;
  raise notice 'Cleaned orderbook data older than % days',days;
end $$;

create or replace function public.cleanup_old_raw_data() returns void
language plpgsql as $$ begin
  delete from public.stock_raw_intraday where fetched_at < now()-interval '1095 days';
  raise notice 'Cleaned raw data older than 3 years';
end $$;

create or replace function public.replace_features_atomic(p_symbol text,p_timeframe text,p_start_utc timestamptz,p_end_exclusive_utc timestamptz,p_replacement_rows jsonb)
returns table(deleted_count bigint,replaced_count bigint) language plpgsql security definer set search_path='' as $function$
declare v_deleted bigint; v_replaced bigint;
begin
  if p_symbol is null or btrim(p_symbol)='' or upper(btrim(p_symbol)) in ('*','%','ALL') or p_symbol ~ '[*,%]' then raise exception 'replace_features_atomic requires one exact symbol'; end if;
  if p_timeframe not in ('1d','15m','60m') then raise exception 'replace_features_atomic rejects timeframe %',p_timeframe; end if;
  if p_start_utc is null or p_end_exclusive_utc is null or p_start_utc>=p_end_exclusive_utc then raise exception 'replace_features_atomic requires a valid half-open UTC range'; end if;
  if p_replacement_rows is null or jsonb_typeof(p_replacement_rows)<>'array' or jsonb_array_length(p_replacement_rows)=0 then raise exception 'replace_features_atomic refuses an empty replacement dataset'; end if;
  if exists(select 1 from jsonb_array_elements(p_replacement_rows) r where r->>'symbol' is distinct from p_symbol or r->>'timeframe' is distinct from p_timeframe or nullif(r->>'time','') is null or (r->>'time')::timestamptz<p_start_utc or (r->>'time')::timestamptz>=p_end_exclusive_utc) then raise exception 'replacement row is invalid or outside the requested scope'; end if;
  if exists(select 1 from jsonb_array_elements(p_replacement_rows) r group by r->>'symbol',r->>'timeframe',(r->>'time')::timestamptz having count(*)>1) then raise exception 'replacement dataset contains duplicate feature keys'; end if;
  delete from public.stock_features where symbol=p_symbol and timeframe=p_timeframe and time>=p_start_utc and time<p_end_exclusive_utc; get diagnostics v_deleted=row_count;
  insert into public.stock_features select populated.* from jsonb_populate_recordset(null::public.stock_features,p_replacement_rows) populated; get diagnostics v_replaced=row_count;
  if v_replaced<>jsonb_array_length(p_replacement_rows) then raise exception 'replacement row count mismatch: expected %, inserted %',jsonb_array_length(p_replacement_rows),v_replaced; end if;
  return query select v_deleted,v_replaced;
end $function$;


-- CREATE OR REPLACE preserves the existing function identity, owner, grants,
-- security mode, and configured search_path of all three functions.

notify pgrst, 'reload schema';
commit;

-- Read-only verification SQL (run after COMMIT):
-- with expected(old_name,new_name) as (values
--   ('raw_daily','stock_raw_daily'),('raw_intraday','stock_raw_intraday'),
--   ('features','stock_features'),('foreign_trading','stock_foreign_trading'),
--   ('orderbook_snapshot','stock_orderbook_snapshot'),('data_quality_logs','stock_data_quality_logs'))
-- select old_name,to_regclass('public.'||old_name) old_relation,
--        new_name,to_regclass('public.'||new_name) new_relation from expected;
-- select c.relname as table_name,c.oid,c.relrowsecurity,c.relforcerowsecurity
-- from pg_class c where c.oid in ('public.stock_raw_daily'::regclass,
--   'public.stock_raw_intraday'::regclass,'public.stock_features'::regclass,
--   'public.stock_foreign_trading'::regclass,'public.stock_orderbook_snapshot'::regclass,
--   'public.stock_data_quality_logs'::regclass) order by c.relname;
-- select conname,conrelid::regclass,confrelid::regclass from pg_constraint
-- where conrelid in ('public.stock_raw_daily'::regclass,'public.stock_raw_intraday'::regclass,
--   'public.stock_features'::regclass,'public.stock_foreign_trading'::regclass,
--   'public.stock_orderbook_snapshot'::regclass,'public.stock_data_quality_logs'::regclass);
-- select pg_get_functiondef(oid) from pg_proc where pronamespace='public'::regnamespace
-- and proname in ('cleanup_old_orderbook','cleanup_old_raw_data','replace_features_atomic');
-- select table_name from information_schema.tables where table_schema='public' and table_name in
-- ('symbols','securities','analog_profiles','analog_snapshots','analog_outcomes','analog_queries',
--  'analog_query_matches','analog_validation_runs','analog_profile_reviews','stream_raw_snapshot',
--  'stream_quote_snapshot','stream_trade_snapshot','stream_foreign_snapshot','stream_index_snapshot',
--  'stream_status_snapshot','stream_bar_snapshot','index_master','index_components','index_raw_daily',
--  'index_daily','index_features_daily') order by table_name;

-- Rollback guidance: pause every scheduled writer, open a transaction, set the
-- same short local lock_timeout, and apply the six ALTER TABLE renames in reverse
-- (new_name -> old_name), after first verifying that each old name is absent.
-- Collision-safely reverse owned sequence/constraint/index names, restore the
-- three function bodies with raw_intraday/features/orderbook_snapshot references,
-- issue NOTIFY pgrst, 'reload schema', and commit. The rollback is metadata-only.
