-- Standardize stock-only table names. Apply manually during a maintenance window
-- with all scheduled writers paused. Renames are metadata-only but take brief
-- ACCESS EXCLUSIVE locks. No rows are copied, rewritten, or removed.
begin;
set local lock_timeout = '5s';

create temporary table stock_table_rename_map(old_name text primary key, new_name text unique) on commit drop;
insert into stock_table_rename_map(old_name,new_name) values
 ('symbols','stock_symbols'),('securities','stock_securities'),
 ('raw_daily','stock_raw_daily'),('raw_intraday','stock_raw_intraday'),
 ('features','stock_features'),('foreign_trading','stock_foreign_trading'),
 ('orderbook_snapshot','stock_orderbook_snapshot'),('data_quality_logs','stock_data_quality_logs'),
 ('analog_profiles','stock_analog_profiles'),('analog_snapshots','stock_analog_snapshots'),
 ('analog_outcomes','stock_analog_outcomes'),('analog_queries','stock_analog_queries'),
 ('analog_query_matches','stock_analog_query_matches'),('analog_validation_runs','stock_analog_validation_runs'),
 ('analog_profile_reviews','stock_analog_profile_reviews'),
 ('stream_quote_snapshot','stock_stream_quote_snapshot'),('stream_trade_snapshot','stock_stream_trade_snapshot'),
 ('stream_foreign_snapshot','stock_stream_foreign_snapshot'),('stream_status_snapshot','stock_stream_status_snapshot'),
 ('stream_bar_snapshot','stock_stream_bar_snapshot');

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

create or replace function public.persist_analog_query_v1(p_query jsonb,p_matches jsonb)
returns setof public.stock_analog_queries language plpgsql security definer set search_path='' as $$
declare v_query public.stock_analog_queries; v_count integer;
begin
  if jsonb_typeof(p_query)<>'object' or jsonb_typeof(p_matches)<>'array' then raise exception 'query must be an object and matches must be an array'; end if;
  insert into public.stock_analog_queries(snapshot_id,profile_code,version,config_hash,symbol,timeframe,checkpoint,as_of_session,status,candidate_count,usable_sample,normalization_parameters,result_statistics,baseline_statistics,input_fingerprint,query_fingerprint,engine_version,executed_at)
  select x.snapshot_id,x.profile_code,x.version,x.config_hash,x.symbol,x.timeframe,x.checkpoint,x.as_of_session,x.status,x.candidate_count,x.usable_sample,x.normalization_parameters,x.result_statistics,x.baseline_statistics,x.input_fingerprint,x.query_fingerprint,x.engine_version,x.executed_at
  from jsonb_to_record(p_query) x(snapshot_id uuid,profile_code text,version integer,config_hash text,symbol text,timeframe text,checkpoint text,as_of_session date,status text,candidate_count integer,usable_sample integer,normalization_parameters jsonb,result_statistics jsonb,baseline_statistics jsonb,input_fingerprint text,query_fingerprint text,engine_version text,executed_at timestamptz)
  on conflict(profile_code,version,config_hash,symbol,checkpoint,as_of_session,query_fingerprint) do update set executed_at=excluded.executed_at returning * into v_query;
  insert into public.stock_analog_query_matches(query_id,rank,matched_snapshot_id,distance,similarity,normalized_differences)
  select v_query.id,x.rank,x.matched_snapshot_id,x.distance,x.similarity,x.normalized_differences from jsonb_to_recordset(p_matches) x(rank integer,matched_snapshot_id uuid,distance double precision,similarity double precision,normalized_differences jsonb)
  on conflict(query_id,rank) do update set matched_snapshot_id=excluded.matched_snapshot_id,distance=excluded.distance,similarity=excluded.similarity,normalized_differences=excluded.normalized_differences;
  get diagnostics v_count=row_count; if v_count<>jsonb_array_length(p_matches) then raise exception 'match count mismatch'; end if; return next v_query;
end $$;

-- Existing grants are retained by CREATE OR REPLACE; restate the restricted RPC grants.
revoke all on function public.persist_analog_query_v1(jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.persist_analog_query_v1(jsonb,jsonb) to service_role;
revoke all on function public.replace_features_atomic(text,text,timestamptz,timestamptz,jsonb) from public,anon,authenticated;
grant execute on function public.replace_features_atomic(text,text,timestamptz,timestamptz,jsonb) to service_role;

-- The renamed policy remains attached to the same table. Replacing it makes its
-- dependency on the renamed query table explicit and verifiable.
drop policy if exists analog_matches_authenticated_read on public.stock_analog_query_matches;
create policy analog_matches_authenticated_read on public.stock_analog_query_matches for select to authenticated
using (exists(select 1 from public.stock_analog_queries q where q.id=query_id and q.status in ('completed','insufficient_sample','not_evaluable')));

notify pgrst, 'reload schema';
commit;

-- Read-only verification SQL:
-- select old_name,to_regclass('public.'||old_name),new_name,to_regclass('public.'||new_name) from stock_table_rename_map; -- run before COMMIT if desired
-- select inhparent::regclass,count(*) from pg_inherits where inhparent='public.stock_intraday'::regclass group by 1;
-- select conname,conrelid::regclass,confrelid::regclass from pg_constraint where confrelid='public.stock_symbols'::regclass;
-- select tablename,policyname,roles,qual from pg_policies where tablename like 'stock_analog_%' order by 1,2;
-- select pg_get_functiondef(oid) from pg_proc where pronamespace='public'::regnamespace and proname in ('cleanup_old_orderbook','cleanup_old_raw_data','persist_analog_query_v1','replace_features_atomic');
-- select table_name,count(*) over() from information_schema.tables where table_schema='public' and table_name in ('index_master','index_raw_daily','index_daily','index_features_daily','index_components','stream_index_snapshot','stream_raw_snapshot');
-- Practical rollback: pause writers in a maintenance window, BEGIN with the same
-- lock_timeout, reverse every new_name -> old_name ALTER TABLE rename, collision-
-- safely reverse renamed constraints/indexes/sequences, restore the four function
-- bodies from their immediately preceding migrations/schema snapshot, restore the
-- query-match policy body to public.analog_queries, NOTIFY pgrst, then COMMIT.
