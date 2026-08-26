-- Read-only verification for migrations/20260827_restore_domain_table_names.sql.
-- Run the count query both immediately before and after the migration and compare
-- the results by logical_name. Observed 2026-08-26 counts are reference evidence,
-- not assertions: stock_raw_daily=1408, stock_raw_intraday=315749,
-- stock_features=31520, analog_profiles=2, analog_snapshots=2786,
-- analog_outcomes=9403, symbols=5.

-- 1-5, 7-8: required/forbidden relations and deliberately unchanged domains.
with expected(name, should_exist) as (values
 ('stock_raw_daily',true),('stock_raw_intraday',true),('stock_features',true),
 ('stock_foreign_trading',true),('stock_orderbook_snapshot',true),('stock_data_quality_logs',true),
 ('raw_daily',false),('raw_intraday',false),('features',false),('foreign_trading',false),
 ('orderbook_snapshot',false),('data_quality_logs',false),
 ('symbols',true),('securities',true),('analog_profiles',true),('analog_snapshots',true),
 ('analog_outcomes',true),('analog_queries',true),('analog_query_matches',true),
 ('analog_validation_runs',true),('analog_profile_reviews',true),
 ('stream_quote_snapshot',true),('stream_trade_snapshot',true),('stream_foreign_snapshot',true),
 ('stream_status_snapshot',true),('stream_bar_snapshot',true),
 ('stock_symbols',false),('stock_securities',false),('stock_analog_profiles',false),
 ('stock_analog_snapshots',false),('stock_analog_outcomes',false),('stock_analog_queries',false),
 ('stock_analog_query_matches',false),('stock_analog_validation_runs',false),
 ('stock_analog_profile_reviews',false),('stock_stream_quote_snapshot',false),
 ('stock_stream_trade_snapshot',false),('stock_stream_foreign_snapshot',false),
 ('stock_stream_status_snapshot',false),('stock_stream_bar_snapshot',false),
 ('stock_daily',true),('stock_intraday',true),('stream_raw_snapshot',true),
 ('stream_index_snapshot',true),('index_master',true),('index_components',true),
 ('index_raw_daily',true),('index_daily',true),('index_features_daily',true))
select name,should_exist,to_regclass(format('public.%I',name)) is not null as actually_exists,
       should_exist=(to_regclass(format('public.%I',name)) is not null) as ok
from expected order by ok,name;

-- 6: every monthly stock_intraday partition remains attached.
select child.relname as partition_name, parent.relname as parent_name,
       pg_get_expr(child.relpartbound,child.oid) as partition_bound
from pg_inherits h join pg_class parent on parent.oid=h.inhparent
join pg_class child on child.oid=h.inhrelid
where parent.oid='public.stock_intraday'::regclass
order by child.relname;

-- 9: must return zero rows.
select conname,conrelid::regclass from pg_constraint where not convalidated;

-- 10: FKs remain OID-bound to symbols, including parent/partitions and Analog.
select c.conname,c.conrelid::regclass as source_table,c.confrelid::regclass as target_table,
       c.convalidated
from pg_constraint c
where c.contype='f' and c.conrelid in (
  select 'public.stock_intraday'::regclass union all
  select inhrelid from pg_inherits where inhparent='public.stock_intraday'::regclass union all
  select 'public.stock_features'::regclass union all
  select 'public.stock_foreign_trading'::regclass union all
  select 'public.analog_snapshots'::regclass)
order by source_table::text,c.conname;

-- 11: RLS flags and policies (names, roles, commands, USING/WITH CHECK) survive.
select c.relname,c.relrowsecurity,c.relforcerowsecurity
from pg_class c where c.relnamespace='public'::regnamespace and c.relname in
 ('analog_profiles','analog_snapshots','analog_outcomes','analog_queries',
  'analog_query_matches','analog_validation_runs','analog_profile_reviews') order by 1;
select tablename,policyname,roles,cmd,qual,with_check from pg_policies
where schemaname='public' and tablename like 'analog\_%' escape '\'
order by tablename,policyname;

-- 12: inspect all four function bodies and privilege/security metadata.
select p.oid::regprocedure,p.prosecdef,p.proconfig,pg_get_functiondef(p.oid),
       p.proacl
from pg_proc p where p.pronamespace='public'::regnamespace and p.proname in
 ('cleanup_old_orderbook','cleanup_old_raw_data','replace_features_atomic','persist_analog_query_v1')
order by p.proname;

-- 13: must return zero rows.
select 'constraint' as kind,conname as object_name from pg_constraint
where connamespace='public'::regnamespace and conname like 'stock\_stock\_%' escape '\'
union all select case relkind when 'S' then 'sequence' else 'index' end,relname
from pg_class where relnamespace='public'::regnamespace and relkind in ('i','I','S')
and relname like 'stock\_stock\_%' escape '\' order by 1,2;

-- 14: capture immediately before and after. This dynamically accepts either side
-- of each corrected mapping and never hardcodes mutable production counts.
with logical(logical_name,before_name,after_name) as (values
 ('stock_raw_daily','stock_raw_daily','stock_raw_daily'),
 ('stock_raw_intraday','stock_raw_intraday','stock_raw_intraday'),
 ('stock_features','stock_features','stock_features'),
 ('analog_profiles','stock_analog_profiles','analog_profiles'),
 ('analog_snapshots','stock_analog_snapshots','analog_snapshots'),
 ('analog_outcomes','stock_analog_outcomes','analog_outcomes'),
 ('symbols','stock_symbols','symbols'))
select format(
  'select %L logical_name, count(*) row_count from public.%I;',
  logical_name,
  case when to_regclass(format('public.%I',after_name)) is not null then after_name else before_name end)
from logical order by logical_name;
