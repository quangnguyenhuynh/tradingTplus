-- Foreign EOD Feature V2: same-symbol stock_daily row windows, without calendars.
begin;

comment on table public.stock_foreign_features_daily is
  'Derived Foreign EOD Feature V2 from rolling same-symbol stock_daily rows; money in VND, ratios stored as fractions.';
comment on column public.stock_foreign_features_daily.source_fingerprint is
  'SHA-256 identity of formula V2, symbol, target date, and the at-most-20 same-symbol source rows affecting metrics/quality.';

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
   select array_agg(x) into unknown_symbols from (
     select distinct upper(btrim(s)) x from unnest(p_symbols) s
     except select symbol from public.symbols
   ) q;
   if unknown_symbols is not null then raise exception 'unknown symbols: %',unknown_symbols; end if;
 end if;
 with scope as (
   select s.symbol,s.market,s.name from public.symbols s where s.status='active'
    and (p_market is null or s.market=p_market)
    and (p_symbols is null or s.symbol=any(select upper(btrim(x)) from unnest(p_symbols)x))
 ), src as (
   select sc.*,d.trading_date,d.foreign_buy_val_total,d.foreign_sell_val_total,
          d.net_foreign_val,d.total_traded_value,
          f.net_value_5d,f.net_value_20d,f.activity_value_5d,f.activity_value_20d,
          f.net_value_ratio_5d,f.net_value_ratio_20d,f.activity_ratio_5d,f.activity_ratio_20d,
          f.buy_days_5d,f.buy_days_20d,f.sell_days_5d,f.sell_days_20d,
          f.net_value_ratio_change_5d,f.activity_ratio_change_5d,
          f.formula_version,f.quality_status,f.source_fingerprint,f.source_window_start,
          e.current_activity_value_5d-e.previous_activity_value_5d emerging_value,
          e.current_activity_ratio_5d-e.previous_activity_ratio_5d emerging_ratio,
          e.valid_rows emerging_valid_rows
   from scope sc
   left join public.stock_daily d on d.symbol=sc.symbol and d.trading_date=p_date
   left join public.stock_foreign_features_daily f on f.symbol=d.symbol and f.trading_date=d.trading_date
   left join lateral (
     with last_ten as (
       select x.*,row_number() over(order by x.trading_date desc) rn
       from public.stock_daily x
       where x.symbol=sc.symbol and x.trading_date<=p_date
       order by x.trading_date desc limit 10
     )
     select count(*) filter(where foreign_buy_val_total is not null
                                  and foreign_sell_val_total is not null
                                  and net_foreign_val=foreign_buy_val_total-foreign_sell_val_total
                                  and total_traded_value is not null and total_traded_value>=0
                                  and not(total_traded_value=0 and foreign_buy_val_total+foreign_sell_val_total>0)) valid_rows,
            sum(foreign_buy_val_total+foreign_sell_val_total) filter(where rn<=5) current_activity_value_5d,
            sum(foreign_buy_val_total+foreign_sell_val_total) filter(where rn>5) previous_activity_value_5d,
            case when sum(total_traded_value) filter(where rn<=5)>0
                 then sum(foreign_buy_val_total+foreign_sell_val_total) filter(where rn<=5)/(2*sum(total_traded_value) filter(where rn<=5)) end current_activity_ratio_5d,
            case when sum(total_traded_value) filter(where rn>5)>0
                 then sum(foreign_buy_val_total+foreign_sell_val_total) filter(where rn>5)/(2*sum(total_traded_value) filter(where rn>5)) end previous_activity_ratio_5d
     from last_ten
   ) e on p_ranking_type='emerging'
 ), metrics as (
   select *,case
    when p_ranking_type='attention' and p_window=1 and p_sort_mode='value' then foreign_buy_val_total+foreign_sell_val_total
    when p_ranking_type in ('accumulation','distribution') and p_window=1 and p_sort_mode='value' then net_foreign_val
    when p_ranking_type='attention' and p_window=5 and p_sort_mode='value' then activity_value_5d
    when p_ranking_type='attention' and p_window=20 and p_sort_mode='value' then activity_value_20d
    when p_ranking_type in ('accumulation','distribution') and p_window=5 and p_sort_mode='value' then net_value_5d
    when p_ranking_type in ('accumulation','distribution') and p_window=20 and p_sort_mode='value' then net_value_20d
    when p_ranking_type='emerging' and p_sort_mode='value' then emerging_value end value_metric,
   case
    when p_window=1 and p_ranking_type='attention' and total_traded_value>0 then (foreign_buy_val_total+foreign_sell_val_total)/(2*total_traded_value)
    when p_window=1 and p_ranking_type in ('accumulation','distribution') and total_traded_value>0 then net_foreign_val/total_traded_value
    when p_window=5 and p_ranking_type='attention' then activity_ratio_5d
    when p_window=20 and p_ranking_type='attention' then activity_ratio_20d
    when p_window=5 and p_ranking_type in ('accumulation','distribution') then net_value_ratio_5d
    when p_window=20 and p_ranking_type in ('accumulation','distribution') then net_value_ratio_20d
    when p_ranking_type='emerging' then emerging_ratio end ratio_metric,
   case when p_window=1 then net_foreign_val when p_window=5 then net_value_5d when p_window=20 then net_value_20d end direction_net
   from src
 ), eligible as (
   select *,case when p_sort_mode='value' then value_metric else ratio_metric end ranking_metric_value
   from metrics where trading_date=p_date
    and foreign_buy_val_total is not null and foreign_sell_val_total is not null
    and net_foreign_val=foreign_buy_val_total-foreign_sell_val_total
    and total_traded_value>=0 and not(total_traded_value=0 and foreign_buy_val_total+foreign_sell_val_total>0)
    and (p_window=1 or (formula_version=2 and source_fingerprint is not null
         and coalesce(quality_status->(p_window::text)->>'status','') in ('VALID','PARTIAL')))
    and (p_ranking_type<>'emerging' or (emerging_valid_rows=10
         and coalesce(quality_status->'change_5d'->>'status','')='VALID'))
 ), filtered as (
   select * from eligible where (case when p_sort_mode='value' then value_metric else ratio_metric end) is not null and
    case when p_ranking_type='attention' then (case when p_sort_mode='value' then value_metric else ratio_metric end)>0
         when p_ranking_type='accumulation' then direction_net>0
         when p_ranking_type='distribution' then direction_net<0
         else (case when p_sort_mode='value' then value_metric else ratio_metric end)>0 end
 ), ranked as (
   select *,rank() over(order by case when p_ranking_type='distribution' then ranking_metric_value end asc nulls last,
                                  case when p_ranking_type<>'distribution' then ranking_metric_value end desc nulls last) ranking_rank from filtered
 ), counts as (
   select (select count(*) from scope) universe_count,
          (select count(*) from src where trading_date=p_date) source_count,
          (select count(*) from eligible) eligible_count,(select count(*) from filtered) result_count
 )
 select jsonb_build_object('meta',jsonb_build_object(
   'requested_date',p_date,'source_mode','EOD','ranking_type',p_ranking_type,'window',p_window,
   'sort',p_sort_mode,'scope_basis',case when p_symbols is null then 'current_active_symbols' else 'explicit_current_active_symbols' end,
   'window_basis','symbol_rows','market',p_market,'formula_version',2,
   'units','VND; ratios=fraction; changes=fraction (x100 = percentage points)',
   'denominator_basis','total_traded_value','universe_count',c.universe_count,
   'source_available_count',c.source_count,'eligible_count',c.eligible_count,
   'result_count_before_pagination',c.result_count,
   'coverage_ratio',case when c.universe_count=0 then null else c.eligible_count::double precision/c.universe_count end,
   'data_status',case when c.eligible_count=c.universe_count then 'OK' else 'PARTIAL' end),
 'rows',coalesce((select jsonb_agg(to_jsonb(z) order by z.ranking_rank,z.symbol) from (
   select ranking_rank rank,symbol,market,trading_date,foreign_buy_val_total,foreign_sell_val_total,
    net_foreign_val,net_value_5d,net_value_20d,activity_value_5d,activity_value_20d,
    net_value_ratio_5d,net_value_ratio_20d,activity_ratio_5d,activity_ratio_20d,
    net_value_ratio_change_5d,activity_ratio_change_5d,ranking_metric_value,
    formula_version,quality_status,source_fingerprint
   from ranked order by ranking_rank,symbol limit p_limit offset p_offset
 )z),'[]'::jsonb)) into result from counts c;
 return result;
end $$;

create or replace function public.get_foreign_symbol_history(p_symbol text,p_to_date date,p_limit integer default 20)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare normalized text:=upper(btrim(p_symbol)); result jsonb;
begin
 if normalized='' or p_to_date is null or p_limit not between 1 and 100 then raise exception 'invalid history arguments'; end if;
 if not exists(select 1 from public.symbols where symbol=normalized and status='active') then raise exception 'unknown or inactive symbol'; end if;
 select jsonb_build_object('meta',jsonb_build_object('symbol',normalized,'to_date',p_to_date,
   'limit',p_limit,'source_mode','EOD','window_basis','symbol_rows','formula_version',2,
   'units','VND; ratios=fraction','denominator_basis','total_traded_value'),
 'rows',coalesce(jsonb_agg(to_jsonb(q) order by q.trading_date desc),'[]'::jsonb)) into result from (
  select d.symbol,d.trading_date,d.foreign_buy_vol_total,d.foreign_sell_vol_total,d.net_foreign_vol,
   d.foreign_buy_val_total,d.foreign_sell_val_total,d.net_foreign_val,d.total_traded_value,
   f.net_value_5d,f.net_value_20d,f.activity_value_5d,f.activity_value_20d,
   f.net_value_ratio_5d,f.net_value_ratio_20d,f.activity_ratio_5d,f.activity_ratio_20d,
   f.buy_days_5d,f.buy_days_20d,f.sell_days_5d,f.sell_days_20d,
   f.net_value_ratio_change_5d,f.activity_ratio_change_5d,f.formula_version,
   f.quality_status,f.source_fingerprint,
   case when f.symbol is null then 'MISSING_FEATURE'
        when f.formula_version<>2 then 'STALE_FORMULA'
        when d.net_foreign_val is distinct from d.foreign_buy_val_total-d.foreign_sell_val_total then 'INVALID_SOURCE'
        else 'CURRENT' end freshness
  from public.stock_daily d left join public.stock_foreign_features_daily f using(symbol,trading_date)
  where d.symbol=normalized and d.trading_date<=p_to_date order by d.trading_date desc limit p_limit
 )q;
 return result;
end $$;

-- Preserve the V1 privilege boundary; do not grant anon or PUBLIC access.
revoke all on function public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer) from public,anon;
revoke all on function public.get_foreign_symbol_history(text,date,integer) from public,anon;
grant execute on function public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer) to authenticated,service_role;
grant execute on function public.get_foreign_symbol_history(text,date,integer) to authenticated,service_role;
commit;

-- Verification (read-only; run after deployment):
-- select pg_get_functiondef('public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)'::regprocedure);
-- select public.get_foreign_ranking(date '2026-08-28','emerging',5,'value',null,array['SSI'],20,0);
-- select public.get_foreign_ranking(date '2026-08-28','emerging',5,'ratio',null,array['SSI'],20,0);
-- select public.get_foreign_symbol_history('SSI',date '2026-08-28',20);
-- select formula_version,count(*) from public.stock_foreign_features_daily group by 1 order by 1;
-- select has_function_privilege('anon','public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)','execute'),
--        has_function_privilege('authenticated','public.get_foreign_ranking(date,text,integer,text,text,text[],integer,integer)','execute');
-- Rollback guidance: redeploy the two function definitions from the prior approved
-- migration. The table and V1/V2 rows need not be dropped; pause publication while
-- code/RPC versions differ. This migration performs no table rewrite or data backfill.
