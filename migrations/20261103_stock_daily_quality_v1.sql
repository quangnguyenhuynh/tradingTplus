-- Owner/manual deployment only. No historical status/value backfill.
BEGIN;
SET LOCAL lock_timeout='5s';
ALTER TABLE public.stock_daily ADD COLUMN IF NOT EXISTS validation_status text;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='public.stock_daily'::regclass AND conname='stock_daily_validation_status_v1_check') THEN
  ALTER TABLE public.stock_daily ADD CONSTRAINT stock_daily_validation_status_v1_check CHECK(validation_status IS NULL OR validation_status IN ('VALID','PARTIAL'));
 END IF;
END $$;
-- Reuse the existing current-issue identity. Existing conflicting rows cause an
-- explicit migration failure; never delete/deduplicate historical logs silently.
CREATE UNIQUE INDEX IF NOT EXISTS stock_data_quality_logs_symbol_date_check_uidx
 ON public.stock_data_quality_logs(symbol,trading_date,check_name);
CREATE OR REPLACE FUNCTION public.persist_stock_daily_validation_v1(
 p_symbol text,p_date date,p_raw_hash text,p_candidate jsonb,p_report jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $function$
DECLARE
 old_row jsonb; merged jsonb; stored jsonb; old_details jsonb; v_details jsonb; history jsonb;
 decision text:=p_report->>'decision'; issues jsonb:=p_report->'issues';
 stamp timestamptz:=(p_report->>'processed_at')::timestamptz; field text; preserved jsonb:='[]'::jsonb;
 written integer:=0; fingerprint text; previous_hash text;
BEGIN
 IF stamp IS NULL THEN RAISE EXCEPTION 'Application processing timestamp required'; END IF;
 IF p_report->>'policy_version' IS DISTINCT FROM 'stock_daily_validation_v1.0.0'
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
 SELECT r.data_hash INTO previous_hash FROM public.stock_raw_daily r
 WHERE r.symbol=p_symbol AND r.trading_date=p_date AND r.payload=old_row->'raw' AND r.source=old_row->>'source' LIMIT 1;
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
COMMIT;
-- Verify: SELECT column_name,is_nullable FROM information_schema.columns
-- WHERE table_schema='public' AND table_name='stock_daily' AND column_name='validation_status';
-- SELECT validation_status,count(*) FROM public.stock_daily GROUP BY 1;
-- SELECT status,details FROM public.stock_data_quality_logs WHERE check_name='stock_daily_validation_v1';
-- Rollback: stop V1 writers, deploy previous app, retain nullable status/log evidence.
-- Only after review: DROP FUNCTION ...; ALTER TABLE public.stock_daily DROP CONSTRAINT stock_daily_validation_status_v1_check;
-- No historical data/status update is performed by this migration.
