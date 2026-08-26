-- Correct the over-broad 20260826 stock-prefix migration. Apply manually in a
-- maintenance window with scheduled GitHub Actions and every database writer
-- paused. ALTER TABLE RENAME is metadata-only but takes brief ACCESS EXCLUSIVE
-- locks. This migration copies, recreates, deletes, and backfills no table data.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '2min';

create temporary table domain_table_restore_map(
  incorrect_name text primary key,
  correct_name text unique not null
) on commit drop;
insert into domain_table_restore_map(incorrect_name, correct_name) values
 ('stock_symbols','symbols'),
 ('stock_securities','securities'),
 ('stock_analog_profiles','analog_profiles'),
 ('stock_analog_snapshots','analog_snapshots'),
 ('stock_analog_outcomes','analog_outcomes'),
 ('stock_analog_queries','analog_queries'),
 ('stock_analog_query_matches','analog_query_matches'),
 ('stock_analog_validation_runs','analog_validation_runs'),
 ('stock_analog_profile_reviews','analog_profile_reviews'),
 ('stock_stream_quote_snapshot','stream_quote_snapshot'),
 ('stock_stream_trade_snapshot','stream_trade_snapshot'),
 ('stock_stream_foreign_snapshot','stream_foreign_snapshot'),
 ('stock_stream_status_snapshot','stream_status_snapshot'),
 ('stock_stream_bar_snapshot','stream_bar_snapshot');

do $restore_tables$
declare item record; incorrect_oid oid; correct_oid oid;
begin
  for item in select * from domain_table_restore_map order by incorrect_name loop
    incorrect_oid := to_regclass(format('public.%I', item.incorrect_name));
    correct_oid := to_regclass(format('public.%I', item.correct_name));
    if incorrect_oid is not null and correct_oid is not null then
      raise exception 'ambiguous domain table restore: both public.% and public.% exist',
        item.incorrect_name, item.correct_name;
    elsif incorrect_oid is null and correct_oid is null then
      raise exception 'missing domain schema: neither public.% nor public.% exists',
        item.incorrect_name, item.correct_name;
    elsif incorrect_oid is not null then
      execute format('alter table public.%I rename to %I', item.incorrect_name, item.correct_name);
    end if;
  end loop;
end $restore_tables$;

-- Normalize only objects owned by/bound to the corrected contract. The desired
-- name is computed once from its owning table's final domain; this is not a
-- repository-wide substring replacement. Every collision aborts the transaction.
create temporary table domain_object_tables(table_name text primary key, desired_prefix text not null) on commit drop;
insert into domain_object_tables values
 ('symbols','symbols'), ('securities','securities'),
 ('analog_profiles','analog_profiles'), ('analog_snapshots','analog_snapshots'),
 ('analog_outcomes','analog_outcomes'), ('analog_queries','analog_queries'),
 ('analog_query_matches','analog_query_matches'),
 ('analog_validation_runs','analog_validation_runs'),
 ('analog_profile_reviews','analog_profile_reviews'),
 ('stream_quote_snapshot','stream_quote_snapshot'),
 ('stream_trade_snapshot','stream_trade_snapshot'),
 ('stream_foreign_snapshot','stream_foreign_snapshot'),
 ('stream_status_snapshot','stream_status_snapshot'),
 ('stream_bar_snapshot','stream_bar_snapshot'),
 ('stock_raw_daily','stock_raw_daily'),
 ('stock_raw_intraday','stock_raw_intraday'),
 ('stock_features','stock_features'),
 ('stock_foreign_trading','stock_foreign_trading'),
 ('stock_orderbook_snapshot','stock_orderbook_snapshot'),
 ('stock_data_quality_logs','stock_data_quality_logs');

create or replace function pg_temp.normalized_object_name(current_name text, desired_prefix text)
returns text language plpgsql immutable strict as $normalize$
declare suffix text := current_name;
begin
  -- Remove malformed repeated prefixes and the former owning-table prefix only.
  while suffix like 'stock_stock_%' loop suffix := substr(suffix, 7); end loop;
  if suffix like 'stock_%' then suffix := substr(suffix, 7); end if;
  if suffix like desired_prefix || '\_%' escape '\' then
    return suffix;
  end if;
  -- Historical names normally retain the complete original table name. Keep
  -- only the object-role suffix when that is identifiable.
  suffix := regexp_replace(suffix,
    '^(symbols|securities|analog_[a-z_]+|stream_[a-z_]+|raw_daily|raw_intraday|features|foreign_trading|orderbook_snapshot|data_quality_logs)_', '');
  return desired_prefix || '_' || suffix;
end $normalize$;

do $constraints$
declare obj record; proposed text;
begin
  for obj in
    select c.conrelid, c.conname, t.table_name, t.desired_prefix
    from domain_object_tables t
    join pg_class r on r.relnamespace='public'::regnamespace and r.relname=t.table_name
    join pg_constraint c on c.conrelid=r.oid
    where c.conname like 'stock\_stock\_%' escape '\'
       or (t.desired_prefix not like 'stock\_%' escape '\' and c.conname like 'stock\_%' escape '\')
  loop
    proposed := pg_temp.normalized_object_name(obj.conname, obj.desired_prefix);
    if exists(select 1 from pg_constraint where conrelid=obj.conrelid and conname=proposed) then
      raise exception 'constraint rename collision on public.%: % -> %', obj.table_name, obj.conname, proposed;
    end if;
    execute format('alter table public.%I rename constraint %I to %I', obj.table_name, obj.conname, proposed);
  end loop;
end $constraints$;

do $indexes$
declare obj record; proposed text;
begin
  for obj in
    select i.indexrelid, x.relname, t.table_name, t.desired_prefix
    from domain_object_tables t
    join pg_class r on r.relnamespace='public'::regnamespace and r.relname=t.table_name
    join pg_index i on i.indrelid=r.oid
    join pg_class x on x.oid=i.indexrelid
    where x.relname like 'stock\_stock\_%' escape '\'
       or (t.desired_prefix not like 'stock\_%' escape '\' and x.relname like 'stock\_%' escape '\')
  loop
    proposed := pg_temp.normalized_object_name(obj.relname, obj.desired_prefix);
    if to_regclass(format('public.%I', proposed)) is not null then
      raise exception 'index rename collision: public.% -> public.%', obj.relname, proposed;
    end if;
    execute format('alter index public.%I rename to %I', obj.relname, proposed);
  end loop;
end $indexes$;

do $sequences$
declare obj record; proposed text;
begin
  for obj in
    select distinct s.relname, t.table_name, t.desired_prefix
    from domain_object_tables t
    join pg_class r on r.relnamespace='public'::regnamespace and r.relname=t.table_name
    join pg_depend d on d.refobjid=r.oid and d.deptype in ('a','i')
    join pg_class s on s.oid=d.objid and s.relkind='S'
    where s.relname like 'stock\_stock\_%' escape '\'
       or (t.desired_prefix not like 'stock\_%' escape '\' and s.relname like 'stock\_%' escape '\')
  loop
    proposed := pg_temp.normalized_object_name(obj.relname, obj.desired_prefix);
    if to_regclass(format('public.%I', proposed)) is not null then
      raise exception 'sequence rename collision: public.% -> public.%', obj.relname, proposed;
    end if;
    execute format('alter sequence public.%I rename to %I', obj.relname, proposed);
  end loop;
end $sequences$;

-- The return relation retains its OID through ALTER TABLE RENAME. Replacing the
-- body corrects stored SQL text while preserving function identity, SECURITY
-- DEFINER, the empty search_path, ownership, and existing EXECUTE grants.
create or replace function public.persist_analog_query_v1(p_query jsonb,p_matches jsonb)
returns setof public.analog_queries language plpgsql security definer set search_path='' as $$
declare v_query public.analog_queries; v_count integer;
begin
  if jsonb_typeof(p_query)<>'object' or jsonb_typeof(p_matches)<>'array' then raise exception 'query must be an object and matches must be an array'; end if;
  insert into public.analog_queries(snapshot_id,profile_code,version,config_hash,symbol,timeframe,checkpoint,as_of_session,status,candidate_count,usable_sample,normalization_parameters,result_statistics,baseline_statistics,input_fingerprint,query_fingerprint,engine_version,executed_at)
  select x.snapshot_id,x.profile_code,x.version,x.config_hash,x.symbol,x.timeframe,x.checkpoint,x.as_of_session,x.status,x.candidate_count,x.usable_sample,x.normalization_parameters,x.result_statistics,x.baseline_statistics,x.input_fingerprint,x.query_fingerprint,x.engine_version,x.executed_at
  from jsonb_to_record(p_query) x(snapshot_id uuid,profile_code text,version integer,config_hash text,symbol text,timeframe text,checkpoint text,as_of_session date,status text,candidate_count integer,usable_sample integer,normalization_parameters jsonb,result_statistics jsonb,baseline_statistics jsonb,input_fingerprint text,query_fingerprint text,engine_version text,executed_at timestamptz)
  on conflict(profile_code,version,config_hash,symbol,checkpoint,as_of_session,query_fingerprint) do update set executed_at=excluded.executed_at returning * into v_query;
  insert into public.analog_query_matches(query_id,rank,matched_snapshot_id,distance,similarity,normalized_differences)
  select v_query.id,x.rank,x.matched_snapshot_id,x.distance,x.similarity,x.normalized_differences from jsonb_to_recordset(p_matches) x(rank integer,matched_snapshot_id uuid,distance double precision,similarity double precision,normalized_differences jsonb)
  on conflict(query_id,rank) do update set matched_snapshot_id=excluded.matched_snapshot_id,distance=excluded.distance,similarity=excluded.similarity,normalized_differences=excluded.normalized_differences;
  get diagnostics v_count=row_count; if v_count<>jsonb_array_length(p_matches) then raise exception 'match count mismatch'; end if; return next v_query;
end $$;

notify pgrst, 'reload schema';
commit;

-- Run sql/verify_restore_domain_table_names.sql before and after this migration.
-- Rollback guidance: do not continue deployment after any failed verification.
-- Because this transaction is atomic, an in-transaction error rolls everything
-- back. After a committed migration, pause writers and collision-check before
-- reversing the 14 ALTER TABLE renames; restore this function body to the
-- stock_analog_* historical form only if the old application is also restored.
-- Object names can remain normalized during rollback because their identities
-- and definitions are unchanged. Reload PostgREST before resuming writers.
