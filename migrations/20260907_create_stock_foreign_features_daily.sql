-- Additive Foreign EOD Feature V1 storage and shared read-only report RPCs.
begin;

create table if not exists public.stock_foreign_features_daily (
  symbol text not null,
  trading_date date not null,
  net_value_5d numeric, net_value_20d numeric,
  activity_value_5d numeric, activity_value_20d numeric,
  net_value_ratio_5d double precision, net_value_ratio_20d double precision,
  activity_ratio_5d double precision, activity_ratio_20d double precision,
  buy_days_5d smallint, buy_days_20d smallint,
  sell_days_5d smallint, sell_days_20d smallint,
  net_value_ratio_change_5d double precision,
  activity_ratio_change_5d double precision,
  formula_version integer not null,
  quality_status jsonb not null,
  source_fingerprint text not null,
  source_window_start date not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint stock_foreign_features_daily_pkey primary key(symbol,trading_date),
  constraint stock_foreign_features_formula_positive check(formula_version > 0),
  constraint stock_foreign_features_activity_nonnegative check(
    (activity_value_5d is null or activity_value_5d >= 0) and
    (activity_value_20d is null or activity_value_20d >= 0)),
  constraint stock_foreign_features_day_counts check(
    (buy_days_5d is null or buy_days_5d between 0 and 5) and
    (sell_days_5d is null or sell_days_5d between 0 and 5) and
    (buy_days_5d is null or sell_days_5d is null or buy_days_5d+sell_days_5d <= 5) and
    (buy_days_20d is null or buy_days_20d between 0 and 20) and
    (sell_days_20d is null or sell_days_20d between 0 and 20) and
    (buy_days_20d is null or sell_days_20d is null or buy_days_20d+sell_days_20d <= 20)),
  constraint stock_foreign_features_ratios_finite check(
    (net_value_ratio_5d is null or net_value_ratio_5d > '-Infinity'::double precision and net_value_ratio_5d < 'Infinity'::double precision) and
    (net_value_ratio_20d is null or net_value_ratio_20d > '-Infinity'::double precision and net_value_ratio_20d < 'Infinity'::double precision) and
    (activity_ratio_5d is null or activity_ratio_5d > '-Infinity'::double precision and activity_ratio_5d < 'Infinity'::double precision) and
    (activity_ratio_20d is null or activity_ratio_20d > '-Infinity'::double precision and activity_ratio_20d < 'Infinity'::double precision) and
    (net_value_ratio_change_5d is null or net_value_ratio_change_5d > '-Infinity'::double precision and net_value_ratio_change_5d < 'Infinity'::double precision) and
    (activity_ratio_change_5d is null or activity_ratio_change_5d > '-Infinity'::double precision and activity_ratio_change_5d < 'Infinity'::double precision))
);
create index if not exists stock_foreign_features_daily_date_idx
  on public.stock_foreign_features_daily(trading_date,symbol);
comment on table public.stock_foreign_features_daily is 'Derived Foreign EOD Feature V1 from stock_daily; money in VND, ratios stored as fractions.';
comment on column public.stock_foreign_features_daily.quality_status is 'Small structured per-window status/reason metadata; never raw payload or arbitrary features.';
comment on column public.stock_foreign_features_daily.source_fingerprint is 'SHA-256 identity generated from formula/calendar/expected sessions/row presence/relevant source values.';

alter table public.stock_foreign_features_daily enable row level security;
revoke all on table public.stock_foreign_features_daily from public, anon, authenticated;
grant select on table public.stock_foreign_features_daily to authenticated;
grant select,insert,update,delete on table public.stock_foreign_features_daily to service_role;
drop policy if exists stock_foreign_features_authenticated_read on public.stock_foreign_features_daily;
create policy stock_foreign_features_authenticated_read on public.stock_foreign_features_daily
  for select to authenticated using (true);

create or replace function public.get_foreign_ranking(
 p_date date, p_ranking_type text, p_window integer default 5,
 p_sort_mode text default 'value', p_market text default null,
 p_symbols text[] default null, p_limit integer default 20, p_offset integer default 0
) returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare result jsonb; unknown_symbols text[];
begin
 if p_date is null then raise exception 'p_date is required'; end if;
 if p_ranking_type not in ('attention','accumulation','distribution','emerging') then raise exception 'invalid p_ranking_type'; end if;
 if p_window not in (1,5,20) then raise exception 'invalid p_window'; end if;
 if p_sort_mode not in ('value','ratio') then raise exception 'invalid p_sort_mode'; end if;
 if p_limit not between 1 and 100 or p_offset < 0 then raise exception 'invalid pagination'; end if;
 if p_ranking_type='emerging' and p_window<>5 then raise exception 'emerging requires window=5'; end if;
 if p_symbols is not null and cardinality(p_symbols)=0 then raise exception 'explicit p_symbols cannot be empty'; end if;
 if p_symbols is not null then
   select array_agg(x) into unknown_symbols from (select distinct upper(btrim(s)) x from unnest(p_symbols) s except select symbol from public.symbols) q;
   if unknown_symbols is not null then raise exception 'unknown symbols: %',unknown_symbols; end if;
 end if;
 with scope as (
   select s.symbol,s.market,s.name from public.symbols s where s.status='active'
    and (p_market is null or s.market=p_market)
    and (p_symbols is null or s.symbol=any(select upper(btrim(x)) from unnest(p_symbols)x))
 ), src as (
   select sc.*,d.trading_date,d.foreign_buy_val_total,d.foreign_sell_val_total,d.net_foreign_val,d.total_traded_value,
          f.net_value_5d,f.net_value_20d,f.activity_value_5d,f.activity_value_20d,f.net_value_ratio_5d,f.net_value_ratio_20d,f.activity_ratio_5d,f.activity_ratio_20d,f.buy_days_5d,f.buy_days_20d,f.sell_days_5d,f.sell_days_20d,f.net_value_ratio_change_5d,f.activity_ratio_change_5d,f.formula_version,f.quality_status,f.source_fingerprint,f.source_window_start,prev.activity_value_5d previous_activity_value_5d
   from scope sc left join public.stock_daily d on d.symbol=sc.symbol and d.trading_date=p_date
   left join public.stock_foreign_features_daily f on f.symbol=d.symbol and f.trading_date=d.trading_date
   left join public.stock_foreign_features_daily prev on prev.symbol=sc.symbol and prev.trading_date=(f.quality_status->'calendar'->'sessions'->>14)::date
 ), metrics as (
   select *, case
    when p_ranking_type='attention' and p_window=1 and p_sort_mode='value' then foreign_buy_val_total+foreign_sell_val_total
    when p_ranking_type in ('accumulation','distribution') and p_window=1 and p_sort_mode='value' then net_foreign_val
    when p_ranking_type='attention' and p_window=5 and p_sort_mode='value' then activity_value_5d
    when p_ranking_type='attention' and p_window=20 and p_sort_mode='value' then activity_value_20d
    when p_ranking_type in ('accumulation','distribution') and p_window=5 and p_sort_mode='value' then net_value_5d
    when p_ranking_type in ('accumulation','distribution') and p_window=20 and p_sort_mode='value' then net_value_20d
    when p_ranking_type='emerging' and p_sort_mode='value' then activity_value_5d-previous_activity_value_5d
   end value_metric,
   case
    when p_window=1 and p_ranking_type='attention' and total_traded_value>0 then (foreign_buy_val_total+foreign_sell_val_total)/(2*total_traded_value)
    when p_window=1 and p_ranking_type in ('accumulation','distribution') and total_traded_value>0 then net_foreign_val/total_traded_value
    when p_window=5 and p_ranking_type='attention' then activity_ratio_5d
    when p_window=20 and p_ranking_type='attention' then activity_ratio_20d
    when p_window=5 and p_ranking_type in ('accumulation','distribution') then net_value_ratio_5d
    when p_window=20 and p_ranking_type in ('accumulation','distribution') then net_value_ratio_20d
    when p_ranking_type='emerging' then activity_ratio_change_5d end ratio_metric,
   case when p_window=1 then net_foreign_val when p_window=5 then net_value_5d when p_window=20 then net_value_20d end direction_net
   from src
 ), eligible as (
   select *,case when p_sort_mode='value' then value_metric else ratio_metric end ranking_metric_value
   from metrics where trading_date=p_date
    and foreign_buy_val_total is not null and foreign_sell_val_total is not null and net_foreign_val=foreign_buy_val_total-foreign_sell_val_total
    and total_traded_value>=0 and not(total_traded_value=0 and foreign_buy_val_total+foreign_sell_val_total>0)
    and (p_window=1 or (formula_version=1 and source_fingerprint is not null and coalesce(quality_status->(p_window::text)->>'status','') in ('VALID','PARTIAL')))
 ), filtered as (
   select * from eligible where (case when p_sort_mode='value' then value_metric else ratio_metric end) is not null and
    case when p_ranking_type='attention' then (case when p_sort_mode='value' then value_metric else ratio_metric end)>0
         when p_ranking_type='accumulation' then direction_net>0
         when p_ranking_type='distribution' then direction_net<0
         else (case when p_sort_mode='value' then value_metric else ratio_metric end)>0 end
 ), ranked as (
   select *,rank() over(order by case when p_ranking_type='distribution' then ranking_metric_value end asc nulls last,
                                  case when p_ranking_type<>'distribution' then ranking_metric_value end desc nulls last) ranking_rank from filtered
 ), counts as (select (select count(*) from scope) universe_count,(select count(*) from src where trading_date=p_date) source_count,(select count(*) from eligible) eligible_count,(select count(*) from filtered) result_count)
 select jsonb_build_object('meta',jsonb_build_object('requested_date',p_date,'source_mode','EOD','ranking_type',p_ranking_type,'window',p_window,'sort',p_sort_mode,'scope_basis',case when p_symbols is null then 'current_active_symbols' else 'explicit_current_active_symbols' end,'market',p_market,'formula_version',1,'units','VND; ratios=fraction; changes=fraction (x100 = percentage points)','denominator_basis','total_traded_value','universe_count',c.universe_count,'source_available_count',c.source_count,'eligible_count',c.eligible_count,'result_count_before_pagination',c.result_count,'coverage_ratio',case when c.universe_count=0 then null else c.eligible_count::double precision/c.universe_count end,'data_status',case when c.eligible_count=c.universe_count then 'OK' else 'PARTIAL' end),
 'rows',coalesce((select jsonb_agg(to_jsonb(z) order by z.ranking_rank,z.symbol) from (select ranking_rank rank,symbol,market,trading_date,foreign_buy_val_total,foreign_sell_val_total,net_foreign_val,net_value_5d,net_value_20d,activity_value_5d,activity_value_20d,net_value_ratio_5d,net_value_ratio_20d,activity_ratio_5d,activity_ratio_20d,net_value_ratio_change_5d,activity_ratio_change_5d,ranking_metric_value,formula_version,quality_status,source_fingerprint from ranked order by ranking_rank,symbol limit p_limit offset p_offset)z),'[]'::jsonb)) into result from counts c;
 return result;
end $$;
revoke all on function public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer) from public,anon;
grant execute on function public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer) to authenticated,service_role;

create or replace function public.get_foreign_symbol_history(p_symbol text,p_to_date date,p_limit integer default 20)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare normalized text:=upper(btrim(p_symbol)); result jsonb;
begin
 if normalized='' or p_to_date is null or p_limit not between 1 and 100 then raise exception 'invalid history arguments'; end if;
 if not exists(select 1 from public.symbols where symbol=normalized and status='active') then raise exception 'unknown or inactive symbol'; end if;
 select jsonb_build_object('meta',jsonb_build_object('symbol',normalized,'to_date',p_to_date,'limit',p_limit,'source_mode','EOD','units','VND; ratios=fraction','denominator_basis','total_traded_value'),
 'rows',coalesce(jsonb_agg(to_jsonb(q) order by q.trading_date desc),'[]'::jsonb)) into result from (
  select d.symbol,d.trading_date,d.foreign_buy_vol_total,d.foreign_sell_vol_total,d.net_foreign_vol,d.foreign_buy_val_total,d.foreign_sell_val_total,d.net_foreign_val,d.total_traded_value,
   f.net_value_5d,f.net_value_20d,f.activity_value_5d,f.activity_value_20d,f.net_value_ratio_5d,f.net_value_ratio_20d,f.activity_ratio_5d,f.activity_ratio_20d,f.buy_days_5d,f.buy_days_20d,f.sell_days_5d,f.sell_days_20d,f.net_value_ratio_change_5d,f.activity_ratio_change_5d,f.formula_version,f.quality_status,f.source_fingerprint,
   case when f.symbol is null then 'MISSING_FEATURE' when f.formula_version<>1 then 'STALE_FORMULA' when d.net_foreign_val is distinct from d.foreign_buy_val_total-d.foreign_sell_val_total then 'INVALID_SOURCE' else 'CURRENT' end freshness
  from public.stock_daily d left join public.stock_foreign_features_daily f using(symbol,trading_date)
  where d.symbol=normalized and d.trading_date<=p_to_date order by d.trading_date desc limit p_limit
 )q;
 return result;
end $$;

revoke all on function public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer) from public,anon;
revoke all on function public.get_foreign_symbol_history(text,date,integer) from public,anon;
grant execute on function public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer) to authenticated,service_role;
grant execute on function public.get_foreign_symbol_history(text,date,integer) to authenticated,service_role;
commit;

-- Verification (read-only):
-- select to_regclass('public.stock_foreign_features_daily');
-- select indexname from pg_indexes where tablename='stock_foreign_features_daily';
-- select has_function_privilege('anon','public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)','execute');
-- select has_function_privilege('authenticated','public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)','execute');
-- select public.get_foreign_ranking(current_date,'attention',1,'value',null,null,20,0);
-- Rollback (only after stopping writers/clients and exporting derived rows if wanted):
-- drop function if exists public.get_foreign_symbol_history(text,date,integer);
-- drop function if exists public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer);
-- drop table if exists public.stock_foreign_features_daily;

-- Read-only verification after commit:
-- select to_regclass('public.stock_foreign_features_daily');
-- select indexname from pg_indexes where schemaname='public' and tablename='stock_foreign_features_daily';
-- select relrowsecurity from pg_class where oid='public.stock_foreign_features_daily'::regclass;
-- select has_table_privilege('anon','public.stock_foreign_features_daily','select'),
--        has_table_privilege('authenticated','public.stock_foreign_features_daily','select'),
--        has_function_privilege('anon','public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)','execute'),
--        has_function_privilege('authenticated','public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)','execute');
-- select symbol,trading_date,count(*) from public.stock_foreign_features_daily group by 1,2 having count(*)>1;
-- Rollback (only after stopping the writer and exporting new derived rows if required):
-- drop function if exists public.get_foreign_symbol_history(text,date,integer);
-- drop function if exists public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer);
-- drop table if exists public.stock_foreign_features_daily;
