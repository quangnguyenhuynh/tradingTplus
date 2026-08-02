-- Atomic, exact-scope replacement for deterministic feature rebuilds.
-- Deploy this migration before deploying application code that enables replace mode.
create or replace function public.replace_features_atomic(
  p_symbol text,
  p_timeframe text,
  p_start_utc timestamptz,
  p_end_exclusive_utc timestamptz,
  p_replacement_rows jsonb
)
returns table(deleted_count bigint, replaced_count bigint)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_deleted bigint;
  v_replaced bigint;
begin
  if p_symbol is null or btrim(p_symbol) = ''
     or upper(btrim(p_symbol)) in ('*', '%', 'ALL')
     or p_symbol ~ '[*,%]' then
    raise exception 'replace_features_atomic requires one exact symbol';
  end if;
  if p_timeframe not in ('1d', '15m', '60m') then
    raise exception 'replace_features_atomic rejects timeframe %', p_timeframe;
  end if;
  if p_start_utc is null or p_end_exclusive_utc is null
     or p_start_utc >= p_end_exclusive_utc then
    raise exception 'replace_features_atomic requires a valid half-open UTC range';
  end if;
  if p_replacement_rows is null
     or jsonb_typeof(p_replacement_rows) <> 'array'
     or jsonb_array_length(p_replacement_rows) = 0 then
    raise exception 'replace_features_atomic refuses an empty replacement dataset';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_replacement_rows) row_value
    where row_value->>'symbol' is distinct from p_symbol
       or row_value->>'timeframe' is distinct from p_timeframe
       or nullif(row_value->>'time', '') is null
       or (row_value->>'time')::timestamptz < p_start_utc
       or (row_value->>'time')::timestamptz >= p_end_exclusive_utc
  ) then
    raise exception 'replacement row is invalid or outside the requested scope';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_replacement_rows) row_value
    group by row_value->>'symbol', row_value->>'timeframe',
             (row_value->>'time')::timestamptz
    having count(*) > 1
  ) then
    raise exception 'replacement dataset contains duplicate feature keys';
  end if;

  delete from public.features
   where symbol = p_symbol
     and timeframe = p_timeframe
     and time >= p_start_utc
     and time < p_end_exclusive_utc;
  get diagnostics v_deleted = row_count;

  insert into public.features
  select populated.*
  from jsonb_populate_recordset(null::public.features, p_replacement_rows) populated;
  get diagnostics v_replaced = row_count;

  if v_replaced <> jsonb_array_length(p_replacement_rows) then
    raise exception 'replacement row count mismatch: expected %, inserted %',
      jsonb_array_length(p_replacement_rows), v_replaced;
  end if;

  return query select v_deleted, v_replaced;
end;
$function$;

revoke all on function public.replace_features_atomic(
  text, text, timestamptz, timestamptz, jsonb
) from public, anon, authenticated;
grant execute on function public.replace_features_atomic(
  text, text, timestamptz, timestamptz, jsonb
) to service_role;

comment on function public.replace_features_atomic(
  text, text, timestamptz, timestamptz, jsonb
) is 'Atomically validates, deletes, and inserts one exact features symbol/timeframe/half-open UTC scope.';

-- Verification (run read-only after deployment):
-- select p.proname, p.prosecdef, p.proconfig, has_function_privilege(
--   'service_role', p.oid, 'EXECUTE') as service_can_execute,
--   has_function_privilege('authenticated', p.oid, 'EXECUTE') as authenticated_can_execute
-- from pg_proc p join pg_namespace n on n.oid=p.pronamespace
-- where n.nspname='public' and p.proname='replace_features_atomic';
--
-- Rollback/cleanup (disables replace mode; does not touch feature rows):
-- drop function if exists public.replace_features_atomic(
--   text, text, timestamptz, timestamptz, jsonb
-- );

