-- Owner/manual deployment. Pause affected daily writers; apply after Stock Daily V1.
-- No NUMERIC type changes, market-value/status rewrites, new tables or backfill.
BEGIN;
SET LOCAL lock_timeout='5s';
CREATE OR REPLACE FUNCTION public.persist_stock_daily_validation_v1(
 p_symbol text,p_date date,p_raw_hash text,p_candidate jsonb,p_report jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $function$
DECLARE
 old_row jsonb; merged jsonb; stored jsonb; old_details jsonb; v_details jsonb; history jsonb;
 decision text:=p_report->>'decision'; issues jsonb:=p_report->'issues';
 stamp timestamptz:=(p_report->>'processed_at')::timestamptz; field text; preserved jsonb:='[]'::jsonb;
 written integer:=0; fingerprint text; previous_hash text; previous_hash_matches integer:=0;
BEGIN
 IF stamp IS NULL THEN RAISE EXCEPTION 'Application processing timestamp required'; END IF;
 IF COALESCE(p_report->>'policy_version','') NOT IN ('stock_daily_validation_v1.0.0','stock_daily_validation_v1.1.0')
 OR decision IS NULL OR decision NOT IN ('VALID','PARTIAL','REJECTED')
 OR jsonb_typeof(issues) IS DISTINCT FROM 'array' THEN
  RAISE EXCEPTION 'Invalid stock daily validation policy report';
 END IF;
 IF (decision='VALID' AND jsonb_array_length(issues)<>0)
 OR (decision<>'VALID' AND jsonb_array_length(issues)=0) THEN
  RAISE EXCEPTION 'Decision and issue count disagree';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.stock_raw_daily r WHERE r.symbol=p_symbol
  AND r.trading_date=p_date AND r.source='ssi_v3' AND r.data_hash=p_raw_hash) THEN
  RAISE EXCEPTION 'RAW reference missing';
 END IF;
 -- Serialize first inserts as well as row updates; no ambiguous application retry.
 PERFORM pg_advisory_xact_lock(hashtextextended(p_symbol||':'||p_date::text,0));
 SELECT to_jsonb(d) INTO old_row FROM public.stock_daily d
 WHERE d.symbol=p_symbol AND d.trading_date=p_date FOR UPDATE;
 SELECT q.details INTO old_details FROM public.stock_data_quality_logs q
 WHERE q.symbol=p_symbol AND q.trading_date=p_date AND q.check_name='stock_daily_validation_v1' FOR UPDATE;
 IF decision<>'REJECTED' THEN
  IF p_candidate->>'symbol' IS DISTINCT FROM p_symbol
   OR (p_candidate->>'trading_date')::date IS DISTINCT FROM p_date
   OR p_candidate->>'source' IS DISTINCT FROM 'ssi_v3'
   OR p_candidate->>'validation_status' IS DISTINCT FROM decision THEN
   RAISE EXCEPTION 'Candidate identity/status mismatch';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM public.stock_raw_daily r WHERE r.symbol=p_symbol AND r.trading_date=p_date AND r.source='ssi_v3' AND r.data_hash=p_raw_hash AND r.payload=p_candidate->'raw') THEN RAISE EXCEPTION 'Candidate RAW payload differs from immutable evidence'; END IF;
  FOR field IN SELECT jsonb_object_keys(p_candidate) LOOP
   IF field <> ALL(ARRAY['symbol','trading_date','price_change','per_price_change','ceiling_price','floor_price','ref_price','open_price','highest_price','lowest_price','close_price','average_price','close_price_adjusted','total_match_vol','total_match_val','total_deal_vol','total_deal_val','total_traded_vol','total_traded_value','foreign_buy_vol_total','foreign_sell_vol_total','foreign_buy_val_total','foreign_sell_val_total','foreign_remaining_room','foreign_total_room','net_foreign_vol','net_foreign_val','total_buy_trade','total_buy_trade_vol','total_sell_trade','total_sell_trade_vol','source','raw','validation_status']) THEN
    RAISE EXCEPTION 'Unknown candidate column';
   END IF;
  END LOOP;
  IF old_row->>'validation_status'='VALID' AND decision='PARTIAL' THEN
   decision:='REJECTED';
   issues:=issues||jsonb_build_array(jsonb_build_object('field',NULL,'code','CLEAN_VALID_DOWNGRADE_BLOCKED',
    'severity','ERROR','action','KEEP_EXISTING_CLEAN','message','Existing VALID row cannot be downgraded by a partial attempt'));
  ELSE
   merged:=COALESCE(old_row,'{}'::jsonb);
   FOR field IN SELECT jsonb_object_keys(p_candidate) LOOP
    -- Only retain independently valid prior numeric inputs. Derived fields are
    -- always recomputed below and must not be reported as retained evidence.
    IF p_candidate->field='null'::jsonb AND old_row->field IS NOT NULL AND old_row->field<>'null'::jsonb
     AND field <> ALL(ARRAY['total_traded_vol','total_traded_value','net_foreign_vol','net_foreign_val'])
     AND old_row->>field NOT IN ('NaN','Infinity','-Infinity')
     AND (CASE WHEN field IN ('price_change','per_price_change') THEN true
      WHEN field IN ('total_match_val','total_deal_val','foreign_buy_val_total','foreign_sell_val_total') THEN (old_row->>field)::numeric>=0
      WHEN field IN ('ceiling_price','floor_price','ref_price','open_price','highest_price','lowest_price','close_price','average_price','close_price_adjusted') THEN (old_row->>field)::numeric>0
      ELSE (old_row->>field)::numeric>=0 AND (old_row->>field)::numeric=trunc((old_row->>field)::numeric) END) THEN
     preserved:=preserved||to_jsonb(field);
    ELSE
     merged:=jsonb_set(merged,ARRAY[field],p_candidate->field,true);
    END IF;
   END LOOP;
   -- Derived values reflect the retained inputs, not a fabricated zero.
   merged:=jsonb_set(merged,'{total_traded_vol}',COALESCE(to_jsonb((merged->>'total_match_vol')::numeric+(merged->>'total_deal_vol')::numeric),'null'::jsonb));
   merged:=jsonb_set(merged,'{total_traded_value}',COALESCE(to_jsonb((merged->>'total_match_val')::numeric+(merged->>'total_deal_val')::numeric),'null'::jsonb));
   merged:=jsonb_set(merged,'{net_foreign_vol}',COALESCE(to_jsonb((merged->>'foreign_buy_vol_total')::numeric-(merged->>'foreign_sell_vol_total')::numeric),'null'::jsonb));
   merged:=jsonb_set(merged,'{net_foreign_val}',COALESCE(to_jsonb((merged->>'foreign_buy_val_total')::numeric-(merged->>'foreign_sell_val_total')::numeric),'null'::jsonb));
   merged:=merged||jsonb_build_object('created_at',CASE WHEN old_row IS NULL THEN to_jsonb(stamp) ELSE old_row->'created_at' END,'updated_at',stamp);
   INSERT INTO public.stock_daily(symbol,trading_date,price_change,per_price_change,ceiling_price,floor_price,ref_price,open_price,highest_price,lowest_price,close_price,average_price,close_price_adjusted,total_match_vol,total_match_val,total_deal_vol,total_deal_val,total_traded_vol,total_traded_value,foreign_buy_vol_total,foreign_sell_vol_total,foreign_buy_val_total,foreign_sell_val_total,foreign_remaining_room,foreign_total_room,net_foreign_vol,net_foreign_val,total_buy_trade,total_buy_trade_vol,total_sell_trade,total_sell_trade_vol,source,raw,validation_status,created_at,updated_at)
   SELECT x.symbol,x.trading_date,x.price_change,x.per_price_change,x.ceiling_price,x.floor_price,x.ref_price,x.open_price,x.highest_price,x.lowest_price,x.close_price,x.average_price,x.close_price_adjusted,x.total_match_vol,x.total_match_val,x.total_deal_vol,x.total_deal_val,x.total_traded_vol,x.total_traded_value,x.foreign_buy_vol_total,x.foreign_sell_vol_total,x.foreign_buy_val_total,x.foreign_sell_val_total,x.foreign_remaining_room,x.foreign_total_room,x.net_foreign_vol,x.net_foreign_val,x.total_buy_trade,x.total_buy_trade_vol,x.total_sell_trade,x.total_sell_trade_vol,x.source,x.raw,x.validation_status,x.created_at,x.updated_at FROM jsonb_populate_record(NULL::public.stock_daily,merged) x
   ON CONFLICT(symbol,trading_date) DO UPDATE SET
    price_change=EXCLUDED.price_change,
    per_price_change=EXCLUDED.per_price_change,
    ceiling_price=EXCLUDED.ceiling_price,
    floor_price=EXCLUDED.floor_price,
    ref_price=EXCLUDED.ref_price,
    open_price=EXCLUDED.open_price,
    highest_price=EXCLUDED.highest_price,
    lowest_price=EXCLUDED.lowest_price,
    close_price=EXCLUDED.close_price,
    average_price=EXCLUDED.average_price,
    close_price_adjusted=EXCLUDED.close_price_adjusted,
    total_match_vol=EXCLUDED.total_match_vol,
    total_match_val=EXCLUDED.total_match_val,
    total_deal_vol=EXCLUDED.total_deal_vol,
    total_deal_val=EXCLUDED.total_deal_val,
    total_traded_vol=EXCLUDED.total_traded_vol,
    total_traded_value=EXCLUDED.total_traded_value,
    foreign_buy_vol_total=EXCLUDED.foreign_buy_vol_total,
    foreign_sell_vol_total=EXCLUDED.foreign_sell_vol_total,
    foreign_buy_val_total=EXCLUDED.foreign_buy_val_total,
    foreign_sell_val_total=EXCLUDED.foreign_sell_val_total,
    foreign_remaining_room=EXCLUDED.foreign_remaining_room,
    foreign_total_room=EXCLUDED.foreign_total_room,
    net_foreign_vol=EXCLUDED.net_foreign_vol,
    net_foreign_val=EXCLUDED.net_foreign_val,
    total_buy_trade=EXCLUDED.total_buy_trade,
    total_buy_trade_vol=EXCLUDED.total_buy_trade_vol,
    total_sell_trade=EXCLUDED.total_sell_trade,
    total_sell_trade_vol=EXCLUDED.total_sell_trade_vol,
    source=EXCLUDED.source,
    raw=EXCLUDED.raw,
    validation_status=EXCLUDED.validation_status,
    updated_at=EXCLUDED.updated_at;
   SELECT to_jsonb(d) INTO stored FROM public.stock_daily d WHERE d.symbol=p_symbol AND d.trading_date=p_date;
   IF stored IS NULL THEN RAISE EXCEPTION 'CLEAN readback missing'; END IF;
   FOR field IN SELECT jsonb_object_keys(p_candidate) LOOP
    IF stored->field IS DISTINCT FROM merged->field THEN RAISE EXCEPTION 'CLEAN readback mismatch'; END IF;
   END LOOP;
   written:=1;
  END IF;
 END IF;
 SELECT CASE WHEN count(*)=1 THEN min(r.data_hash) ELSE NULL END,count(*) INTO previous_hash,previous_hash_matches
 FROM public.stock_raw_daily r WHERE r.symbol=p_symbol AND r.trading_date=p_date
 AND r.payload=old_row->'raw' AND r.source=old_row->>'source';
 SELECT COALESCE(jsonb_agg(CASE WHEN preserved ? (i->>'field') THEN i||jsonb_build_object('action','KEEP_EXISTING_FIELD') ELSE i END),'[]'::jsonb) INTO issues FROM jsonb_array_elements(issues) i;
 fingerprint:=md5(jsonb_build_object('raw_hash',p_raw_hash,'policy',p_report->>'policy_version','decision',decision,'issues',issues,'preserved_fields',preserved)::text);
 history:=COALESCE(old_details->'history','[]'::jsonb);
 IF old_details IS NOT NULL AND old_details->>'fingerprint' IS DISTINCT FROM fingerprint
 AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(history) h WHERE h->>'fingerprint'=old_details->>'fingerprint') THEN
  history:=history||jsonb_build_array(old_details-'history');
 END IF;
 v_details:=jsonb_build_object('dataset','stock_daily','source','ssi_v3','raw_hash',p_raw_hash,'evaluated_at',stamp,
  'policy_version',p_report->>'policy_version','mapping_version',p_report->>'mapping_version',
  'contract_version',p_report->>'contract_version','decision',decision,'source_decision',p_report->>'decision',
  'issues',issues,'preserved_fields',preserved,'previous_clean_raw_hash',previous_hash,
  'previous_clean_raw_hash_match_count',previous_hash_matches,
  'clean_persistence_permitted',written=1,'fingerprint',fingerprint,'history',history);
 IF jsonb_array_length(issues)>0 THEN
  INSERT INTO public.stock_data_quality_logs(symbol,trading_date,timeframe,check_name,severity,status,issue_count,details,created_at)
  VALUES(p_symbol,p_date,'1d','stock_daily_validation_v1',CASE WHEN EXISTS(SELECT 1 FROM jsonb_array_elements(issues) i WHERE i->>'severity'='ERROR') THEN 'ERROR' ELSE 'WARNING' END,'ACTIVE',jsonb_array_length(issues),v_details,stamp)
  ON CONFLICT(symbol,trading_date,check_name) DO UPDATE SET severity=EXCLUDED.severity,status='ACTIVE',
   issue_count=EXCLUDED.issue_count,details=EXCLUDED.details;
 ELSIF old_details IS NOT NULL THEN
  UPDATE public.stock_data_quality_logs SET status='RESOLVED',issue_count=0,details=v_details||jsonb_build_object('resolved_at',stamp)
  WHERE symbol=p_symbol AND trading_date=p_date AND check_name='stock_daily_validation_v1';
 END IF;
 IF jsonb_array_length(issues)>0 OR old_details IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM public.stock_data_quality_logs q WHERE q.symbol=p_symbol AND q.trading_date=p_date
   AND q.check_name='stock_daily_validation_v1' AND q.details->>'fingerprint'=fingerprint
   AND q.status=CASE WHEN jsonb_array_length(issues)>0 THEN 'ACTIVE' ELSE 'RESOLVED' END) THEN
   RAISE EXCEPTION 'Quality log readback missing or different';
  END IF;
 END IF;
 RETURN jsonb_build_object('decision' ,decision,'clean_rows',written,'issue_count',jsonb_array_length(issues),
  'preserved_fields',preserved,'issues',issues,'raw_hash',p_raw_hash,'atomic',true);
END $function$;
REVOKE ALL ON FUNCTION public.persist_stock_daily_validation_v1(text,date,text,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.persist_stock_daily_validation_v1(text,date,text,jsonb,jsonb) TO service_role;

-- Daily-only JSON text transport: JSON number tokens stay numeric in RAW JSONB.
CREATE OR REPLACE FUNCTION public.persist_daily_raw_numeric_v1(p_dataset text,p_rows_json text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $function$
DECLARE rows jsonb:=p_rows_json::jsonb; r jsonb; total integer:=0;
BEGIN
 IF p_dataset NOT IN ('stock_daily','index_daily') OR p_dataset IS NULL
 OR jsonb_typeof(rows) IS DISTINCT FROM 'array' OR jsonb_array_length(rows) NOT BETWEEN 1 AND 1000 THEN
  RAISE EXCEPTION 'Invalid daily RAW batch';
 END IF;
 FOR r IN SELECT * FROM jsonb_array_elements(rows) LOOP
  IF r->>'data_hash' IS NULL OR r->>'data_hash' !~ '^[a-f0-9]{64}$'
  OR r->>'trading_date' IS NULL OR r->>'created_at' IS NULL OR r->>'fetched_at' IS NULL
  OR NOT (r ? 'payload') THEN RAISE EXCEPTION 'Invalid daily RAW identity/audit fields'; END IF;
  IF p_dataset='stock_daily' THEN
   IF r->>'source' IS DISTINCT FROM 'ssi_v3' THEN RAISE EXCEPTION 'Unsupported stock RAW source'; END IF;
   INSERT INTO public.stock_raw_daily(symbol,trading_date,source,data_hash,payload,created_at,fetched_at)
   VALUES(r->>'symbol',(r->>'trading_date')::date,r->>'source',r->>'data_hash',r->'payload',
          (r->>'created_at')::timestamptz,(r->>'fetched_at')::timestamptz)
   ON CONFLICT(symbol,trading_date,source,data_hash) DO NOTHING;
   IF NOT EXISTS(SELECT 1 FROM public.stock_raw_daily d WHERE d.symbol=r->>'symbol' AND d.trading_date=(r->>'trading_date')::date
    AND d.source=r->>'source' AND d.data_hash=r->>'data_hash' AND d.payload=r->'payload') THEN
    RAISE EXCEPTION 'Stock RAW immutable readback mismatch'; END IF;
  ELSE
   IF r->>'source' IS DISTINCT FROM 'SSI_v3_indexSummary' THEN RAISE EXCEPTION 'Unsupported index RAW source'; END IF;
   INSERT INTO public.index_raw_daily(index_code,trading_date,source,data_hash,payload,created_at,fetched_at)
   VALUES(r->>'index_code',(r->>'trading_date')::date,r->>'source',r->>'data_hash',r->'payload',
          (r->>'created_at')::timestamptz,(r->>'fetched_at')::timestamptz)
   ON CONFLICT(index_code,trading_date,data_hash) DO NOTHING;
   IF NOT EXISTS(SELECT 1 FROM public.index_raw_daily d WHERE d.index_code=r->>'index_code' AND d.trading_date=(r->>'trading_date')::date
    AND d.source=r->>'source' AND d.data_hash=r->>'data_hash' AND d.payload=r->'payload') THEN
    RAISE EXCEPTION 'Index RAW immutable readback mismatch'; END IF;
  END IF;
  total:=total+1;
 END LOOP;
 RETURN jsonb_build_object('rows_verified',total,'immutable',true,'exact',true);
END $function$;
REVOKE ALL ON FUNCTION public.persist_daily_raw_numeric_v1(text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.persist_daily_raw_numeric_v1(text,text) TO service_role;

-- Maintain the V1 public function and audit identity; text wrapper avoids any
-- Decimal->float/string substitution inside JSONB candidates and original RAW.
CREATE OR REPLACE FUNCTION public.persist_stock_daily_numeric_v1(
 p_symbol text,p_date date,p_raw_hash text,p_candidate_json text,p_report_json text)
RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $function$
 SELECT public.persist_stock_daily_validation_v1(p_symbol,p_date,p_raw_hash,p_candidate_json::jsonb,p_report_json::jsonb)
$function$;
REVOKE ALL ON FUNCTION public.persist_stock_daily_numeric_v1(text,date,text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.persist_stock_daily_numeric_v1(text,date,text,text,text) TO service_role;

CREATE OR REPLACE FUNCTION public.persist_index_daily_numeric_v1(
 p_code text,p_date date,p_raw_hash text,p_candidate_json text,p_report_json text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $function$
DECLARE candidate jsonb:=p_candidate_json::jsonb; report jsonb:=p_report_json::jsonb;
 old_row jsonb; merged jsonb; stored jsonb; field text; value numeric;
 preserved jsonb:='[]'::jsonb; merged_issues jsonb:='[]'::jsonb;
 total_field text; left_field text; right_field text; operation text; issue_code text; expected numeric;
BEGIN
 IF p_code IS NULL OR p_code<>upper(p_code) OR candidate->>'index_code' IS DISTINCT FROM p_code
 OR (candidate->>'trading_date')::date IS DISTINCT FROM p_date
 OR report->>'policy_version' IS DISTINCT FROM 'index_daily_numeric_v1.0.0'
 OR COALESCE(report->>'decision','') NOT IN ('VALID','VALID_WITH_WARNINGS') THEN
  RAISE EXCEPTION 'Invalid index daily accepted scope/policy';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.index_raw_daily r WHERE r.index_code=p_code
 AND r.trading_date=p_date AND r.source='SSI_v3_indexSummary' AND r.data_hash=p_raw_hash) THEN
  RAISE EXCEPTION 'Index RAW reference missing';
 END IF;
 FOR field IN SELECT jsonb_object_keys(candidate) LOOP
  IF field <> ALL(ARRAY['index_code','trading_date','index_value','index_change','index_change_percentage','total_trade_volume','total_trade_value','total_match_volume','total_match_value','total_deal_volume','total_deal_value','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_buy_value','total_prop_sell_volume','total_prop_sell_value','total_foreign_buy_volume','total_foreign_buy_value','total_foreign_sell_volume','total_foreign_sell_value','net_foreign_purchase_volume','net_foreign_purchase_value']) THEN RAISE EXCEPTION 'Unknown index candidate column'; END IF;
  IF field=ANY(ARRAY['index_value','index_change','index_change_percentage','total_trade_volume','total_trade_value','total_match_volume','total_match_value','total_deal_volume','total_deal_value','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_buy_value','total_prop_sell_volume','total_prop_sell_value','total_foreign_buy_volume','total_foreign_buy_value','total_foreign_sell_volume','total_foreign_sell_value','net_foreign_purchase_volume','net_foreign_purchase_value']) AND candidate->field<>'null'::jsonb THEN
   IF jsonb_typeof(candidate->field)<>'number' THEN RAISE EXCEPTION 'Index numeric JSON token required'; END IF;
   value:=(candidate->>field)::numeric;
   IF value::text IN ('NaN','Infinity','-Infinity')
    OR (field='index_value' AND value<=0)
    OR (field=ANY(ARRAY['total_trade_volume','total_trade_value','total_match_volume','total_match_value','total_deal_volume','total_deal_value','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_buy_value','total_prop_sell_volume','total_prop_sell_value','total_foreign_buy_volume','total_foreign_buy_value','total_foreign_sell_volume','total_foreign_sell_value']) AND value<0)
    OR (field=ANY(ARRAY['total_trade_volume','total_match_volume','total_deal_volume','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_sell_volume','total_foreign_buy_volume','total_foreign_sell_volume','net_foreign_purchase_volume']) AND value<>trunc(value)) THEN RAISE EXCEPTION 'Invalid index numeric input'; END IF;
  END IF;
 END LOOP;
 IF candidate->>'index_value' IS NULL THEN RAISE EXCEPTION 'Index level required'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('index_daily:'||p_code||':'||p_date::text,0));
 SELECT to_jsonb(d) INTO old_row FROM public.index_daily d WHERE d.index_code=p_code AND d.trading_date=p_date FOR UPDATE;
 merged:=COALESCE(old_row,'{}'::jsonb);
 FOR field IN SELECT jsonb_object_keys(candidate) LOOP
  IF candidate->field='null'::jsonb AND field=ANY(ARRAY['index_value','index_change','index_change_percentage','total_trade_volume','total_trade_value','total_match_volume','total_match_value','total_deal_volume','total_deal_value','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_buy_value','total_prop_sell_volume','total_prop_sell_value','total_foreign_buy_volume','total_foreign_buy_value','total_foreign_sell_volume','total_foreign_sell_value','net_foreign_purchase_volume','net_foreign_purchase_value']) AND old_row->>field IS NOT NULL
  AND old_row->>field NOT IN ('NaN','Infinity','-Infinity')
  AND (field<>ALL(ARRAY['total_trade_volume','total_trade_value','total_match_volume','total_match_value','total_deal_volume','total_deal_value','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_buy_value','total_prop_sell_volume','total_prop_sell_value','total_foreign_buy_volume','total_foreign_buy_value','total_foreign_sell_volume','total_foreign_sell_value']) OR (old_row->>field)::numeric>=0)
  AND (field<>ALL(ARRAY['total_trade_volume','total_match_volume','total_deal_volume','total_advance_stock','total_ceiling_stock','total_decline_stock','total_floor_stock','total_no_change_stock','total_prop_buy_volume','total_prop_sell_volume','total_foreign_buy_volume','total_foreign_sell_volume','net_foreign_purchase_volume']) OR (old_row->>field)::numeric=trunc((old_row->>field)::numeric)) THEN
   preserved:=preserved||to_jsonb(field);
  ELSE merged:=jsonb_set(merged,ARRAY[field],candidate->field,true); END IF;
 END LOOP;
 -- Retained inputs can come from an earlier RAW version. Recheck exact
 -- relationships after merge and disclose inconsistencies without fabricating
 -- replacement source totals or silently claiming a fully current source row.
 IF jsonb_array_length(preserved)>0 THEN
  FOR total_field,left_field,right_field,operation,issue_code IN SELECT * FROM (VALUES
   ('total_trade_volume','total_match_volume','total_deal_volume','add','INDEX_TOTAL_COMPONENT_MISMATCH'),
   ('total_trade_value','total_match_value','total_deal_value','add','INDEX_TOTAL_COMPONENT_MISMATCH'),
   ('net_foreign_purchase_volume','total_foreign_buy_volume','total_foreign_sell_volume','subtract','INDEX_FOREIGN_NET_MISMATCH'),
   ('net_foreign_purchase_value','total_foreign_buy_value','total_foreign_sell_value','subtract','INDEX_FOREIGN_NET_MISMATCH')
  ) AS relation(t,l,r,op,code) LOOP
   IF merged->>total_field IS NOT NULL AND merged->>left_field IS NOT NULL AND merged->>right_field IS NOT NULL THEN
    expected:=CASE WHEN operation='add' THEN (merged->>left_field)::numeric+(merged->>right_field)::numeric
                   ELSE (merged->>left_field)::numeric-(merged->>right_field)::numeric END;
    IF (merged->>total_field)::numeric<>expected THEN
     merged_issues:=merged_issues||jsonb_build_array(jsonb_build_object('field',total_field,'code',issue_code,
      'severity','WARNING','action','KEEP_EXACT_MIXED_PROVENANCE','actual_value',merged->>total_field,'expected_value',expected::text));
    END IF;
   END IF;
  END LOOP;
 END IF;
 INSERT INTO public.index_daily(index_code,trading_date,index_value,index_change,index_change_percentage,total_trade_volume,total_trade_value,total_match_volume,total_match_value,total_deal_volume,total_deal_value,total_advance_stock,total_ceiling_stock,total_decline_stock,total_floor_stock,total_no_change_stock,total_prop_buy_volume,total_prop_buy_value,total_prop_sell_volume,total_prop_sell_value,total_foreign_buy_volume,total_foreign_buy_value,total_foreign_sell_volume,total_foreign_sell_value,net_foreign_purchase_volume,net_foreign_purchase_value)
 SELECT x.index_code,x.trading_date,x.index_value,x.index_change,x.index_change_percentage,x.total_trade_volume,x.total_trade_value,x.total_match_volume,x.total_match_value,x.total_deal_volume,x.total_deal_value,x.total_advance_stock,x.total_ceiling_stock,x.total_decline_stock,x.total_floor_stock,x.total_no_change_stock,x.total_prop_buy_volume,x.total_prop_buy_value,x.total_prop_sell_volume,x.total_prop_sell_value,x.total_foreign_buy_volume,x.total_foreign_buy_value,x.total_foreign_sell_volume,x.total_foreign_sell_value,x.net_foreign_purchase_volume,x.net_foreign_purchase_value FROM jsonb_populate_record(NULL::public.index_daily,merged) x
 ON CONFLICT(index_code,trading_date) DO UPDATE SET
 index_value=EXCLUDED.index_value,index_change=EXCLUDED.index_change,index_change_percentage=EXCLUDED.index_change_percentage,total_trade_volume=EXCLUDED.total_trade_volume,total_trade_value=EXCLUDED.total_trade_value,total_match_volume=EXCLUDED.total_match_volume,total_match_value=EXCLUDED.total_match_value,total_deal_volume=EXCLUDED.total_deal_volume,total_deal_value=EXCLUDED.total_deal_value,total_advance_stock=EXCLUDED.total_advance_stock,total_ceiling_stock=EXCLUDED.total_ceiling_stock,total_decline_stock=EXCLUDED.total_decline_stock,total_floor_stock=EXCLUDED.total_floor_stock,total_no_change_stock=EXCLUDED.total_no_change_stock,total_prop_buy_volume=EXCLUDED.total_prop_buy_volume,total_prop_buy_value=EXCLUDED.total_prop_buy_value,total_prop_sell_volume=EXCLUDED.total_prop_sell_volume,total_prop_sell_value=EXCLUDED.total_prop_sell_value,total_foreign_buy_volume=EXCLUDED.total_foreign_buy_volume,total_foreign_buy_value=EXCLUDED.total_foreign_buy_value,total_foreign_sell_volume=EXCLUDED.total_foreign_sell_volume,total_foreign_sell_value=EXCLUDED.total_foreign_sell_value,net_foreign_purchase_volume=EXCLUDED.net_foreign_purchase_volume,net_foreign_purchase_value=EXCLUDED.net_foreign_purchase_value;
 SELECT to_jsonb(d) INTO stored FROM public.index_daily d WHERE d.index_code=p_code AND d.trading_date=p_date;
 IF stored IS NULL THEN RAISE EXCEPTION 'Index CLEAN readback missing'; END IF;
 FOR field IN SELECT jsonb_object_keys(candidate) LOOP
  IF stored->field IS DISTINCT FROM merged->field THEN RAISE EXCEPTION 'Index CLEAN readback mismatch'; END IF;
 END LOOP;
 RETURN jsonb_build_object('decision',CASE WHEN jsonb_array_length(merged_issues)>0 THEN 'VALID_WITH_WARNINGS' ELSE report->>'decision' END,'clean_rows',1,'raw_hash',p_raw_hash,
                          'preserved_fields',preserved,'merge_issues',merged_issues,'exact',true);
END $function$;
REVOKE ALL ON FUNCTION public.persist_index_daily_numeric_v1(text,date,text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.persist_index_daily_numeric_v1(text,date,text,text,text) TO service_role;

-- Read-only exact JSON text responses prevent the SDK's JSON decoder from
-- rounding PostgreSQL NUMERIC/RAW numeric tokens before diagnostics see them.
CREATE OR REPLACE FUNCTION public.read_daily_numeric_scope_v1(
 p_dataset text,p_kind text,p_identifiers text[],p_from date,p_to date,p_offset integer DEFAULT 0,p_limit integer DEFAULT 100)
RETURNS text LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path='' AS $function$
DECLARE table_name text; identity_column text; ordering text; extra text:=''; answer text;
BEGIN
 IF p_dataset IS NULL OR p_dataset NOT IN ('stock_daily','index_daily')
 OR p_kind IS NULL OR p_kind NOT IN ('raw','clean','issues') OR p_from IS NULL OR p_to IS NULL
 OR p_to<p_from OR p_to-p_from>30 OR COALESCE(cardinality(p_identifiers),0) NOT BETWEEN 1 AND 50
 OR p_offset IS NULL OR p_offset NOT BETWEEN 0 AND 9900 OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 100 THEN
  RAISE EXCEPTION 'Invalid bounded daily audit scope'; END IF;
 IF p_kind='issues' AND p_dataset='index_daily' THEN RETURN '{"available":false,"total":0,"rows":[]}'; END IF;
 identity_column:=CASE WHEN p_dataset='stock_daily' THEN 'symbol' ELSE 'index_code' END;
 table_name:=CASE WHEN p_kind='issues' THEN 'stock_data_quality_logs'
 WHEN p_kind='clean' THEN p_dataset WHEN p_dataset='stock_daily' THEN 'stock_raw_daily' ELSE 'index_raw_daily' END;
 ordering:=format('t.%I,t.trading_date',identity_column);
 IF p_kind='raw' THEN ordering:=ordering||',t.source,t.data_hash'; END IF;
 IF p_kind='issues' THEN extra:=' AND t.check_name=''stock_daily_validation_v1'''; END IF;
 EXECUTE format('SELECT jsonb_build_object(''available'',true,''total'',(SELECT count(*) FROM public.%I t WHERE upper(t.%I)=ANY($1) AND t.trading_date BETWEEN $2 AND $3 %s),''rows'',COALESCE((SELECT jsonb_agg(x.row_data) FROM (SELECT to_jsonb(t) AS row_data FROM public.%I t WHERE upper(t.%I)=ANY($1) AND t.trading_date BETWEEN $2 AND $3 %s ORDER BY %s LIMIT $4 OFFSET $5)x),''[]''::jsonb))::text',table_name,identity_column,extra,table_name,identity_column,extra,ordering)
 INTO answer USING p_identifiers,p_from,p_to,p_limit,p_offset;
 RETURN answer;
END $function$;
REVOKE ALL ON FUNCTION public.read_daily_numeric_scope_v1(text,text,text[],date,date,integer,integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.read_daily_numeric_scope_v1(text,text,text[],date,date,integer,integer) TO service_role;

NOTIFY pgrst, 'reload schema';
COMMIT;
-- Verification/rollback and compatibility: docs/DAILY_NUMERIC_PRECISION.md (EN/VI).
-- Rollback app first with writers paused, retain RAW/log evidence; restore prior
-- V1 function from 20261103 only after explicit compatibility review. No data delete.
