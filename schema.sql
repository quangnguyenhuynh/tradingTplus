


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."check_data_freshness"("p_symbol" "text", "p_max_lag_minutes" integer DEFAULT 5) RETURNS TABLE("symbol" "text", "latest_time" timestamp with time zone, "lag_minutes" integer, "is_fresh" boolean)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.symbol,
        MAX(s.time) as latest_time,
        EXTRACT(EPOCH FROM (NOW() - MAX(s.time)))/60 AS lag_minutes,
        (EXTRACT(EPOCH FROM (NOW() - MAX(s.time)))/60) <= p_max_lag_minutes AS is_fresh
    FROM stock_intraday s
    WHERE s.symbol = p_symbol
    GROUP BY s.symbol;
END;
$$;


ALTER FUNCTION "public"."check_data_freshness"("p_symbol" "text", "p_max_lag_minutes" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."cleanup_old_orderbook"("days" integer DEFAULT 14) RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    DELETE FROM stock_orderbook_snapshot WHERE time < NOW() - (days || ' days')::INTERVAL;
    RAISE NOTICE 'Cleaned orderbook data older than % days', days;
END;
$$;


ALTER FUNCTION "public"."cleanup_old_orderbook"("days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."cleanup_old_raw_data"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    DELETE FROM stock_raw_intraday WHERE fetched_at < NOW() - INTERVAL '1095 days';
    RAISE NOTICE 'Cleaned raw data older than 3 years';
END;
$$;


ALTER FUNCTION "public"."cleanup_old_raw_data"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."create_partition_if_not_exists"("p_table" "text", "p_time" timestamp with time zone) RETURNS "void"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    start_date DATE;
    end_date DATE;
    partition_name TEXT;
BEGIN
    start_date := date_trunc('month', p_time)::DATE;
    end_date := (start_date + INTERVAL '1 month')::DATE;
    partition_name := p_table || '_' || to_char(start_date, 'YYYY_MM');
    
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        partition_name, p_table, start_date, end_date
    );
END;
$$;


ALTER FUNCTION "public"."create_partition_if_not_exists"("p_table" "text", "p_time" timestamp with time zone) OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";

-- Post-20260826 stock-domain relation inventory. Definitions introduced by the
-- later focused migrations retain their columns, constraints, RLS, grants, and
-- policies under these metadata-renamed relations:
-- symbols, securities, stock_raw_daily, stock_raw_intraday,
-- stock_daily, stock_intraday, stock_features, stock_foreign_trading,
-- stock_orderbook_snapshot, stock_data_quality_logs,
-- analog_profiles, analog_snapshots, analog_outcomes,
-- analog_queries, analog_query_matches,
-- analog_validation_runs, analog_profile_reviews,
-- stream_quote_snapshot, stream_trade_snapshot,
-- stream_foreign_snapshot, stream_status_snapshot,
-- stream_bar_snapshot. Index-domain relations index_master, index_components,
-- index_raw_daily, index_daily, and index_features_daily, plus the mixed-domain
-- stream_raw_snapshot and stream_index_snapshot are intentionally unchanged.

CREATE TABLE IF NOT EXISTS "public"."index_master" (
    "index_code" text NOT NULL PRIMARY KEY, "index_name" text, "exchange" text,
    "raw" jsonb, "status" text NOT NULL DEFAULT 'active',
    "updated_at" timestamp with time zone,
    CONSTRAINT "index_master_status_check" CHECK ("status" IN ('active', 'inactive'))
);
CREATE TABLE IF NOT EXISTS "public"."index_components" (
    "index_code" text NOT NULL, "symbol" text NOT NULL, "exchange" text,
    "raw" jsonb, "updated_at" timestamp with time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS index_components_index_code_symbol_uidx ON public.index_components(index_code,symbol);
CREATE TABLE IF NOT EXISTS "public"."index_raw_daily" (
    "index_code" text NOT NULL, "trading_date" date NOT NULL, "data_hash" text NOT NULL,
    "payload" jsonb NOT NULL, "source" text NOT NULL, "fetched_at" timestamp with time zone,
    "created_at" timestamp with time zone NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS index_raw_daily_identity_uidx ON public.index_raw_daily(index_code,trading_date,data_hash);
CREATE TABLE IF NOT EXISTS "public"."index_daily" (
    "index_code" text NOT NULL, "trading_date" date NOT NULL, "index_value" numeric,
    "change" numeric, "ratio_change" numeric, "total_trade" numeric,
    "total_match_vol" numeric, "total_match_val" numeric, "total_deal_vol" numeric,
    "total_deal_val" numeric, "total_vol" numeric, "total_val" numeric,
    "type_index" text, "index_name" text, "advances" numeric, "no_changes" numeric,
    "declines" numeric, "ceilings" numeric, "floors" numeric,
    "trading_session" text, "market" text, "exchange" text
);
CREATE UNIQUE INDEX IF NOT EXISTS index_daily_index_code_trading_date_uidx ON public.index_daily(index_code,trading_date);


CREATE TABLE IF NOT EXISTS "public"."stock_features" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision, "high" double precision, "low" double precision, "close" double precision,
    "volume" bigint, "value" bigint,
    "return_1m" double precision, "return_5m" double precision, "return_15m" double precision,
    "return_from_open" double precision, "return_from_prev_close" double precision,
    "ema9" double precision, "ema20" double precision, "ema50" double precision,
    "ema9_above_ema20" boolean, "ema20_above_ema50" boolean,
    "rsi14" double precision, "macd" double precision, "macd_signal" double precision, "macd_histogram" double precision,
    "volume_ma20" double precision, "volume_ratio" double precision,
    "value_ma20" double precision, "value_ratio" double precision,
    "high_20_bars" double precision, "low_20_bars" double precision,
    "close_above_high_20" boolean, "close_below_low_20" boolean,
    "vwap_intraday" double precision, "close_above_vwap" boolean, "distance_to_vwap_pct" double precision,
    "candle_range" double precision, "candle_body" double precision,
    "candle_body_pct" double precision, "close_position_in_candle" double precision,
    "last_updated_at" timestamp with time zone NOT NULL
);


ALTER TABLE "public"."stock_features" OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."replace_features_atomic"(
    "p_symbol" text,
    "p_timeframe" text,
    "p_start_utc" timestamp with time zone,
    "p_end_exclusive_utc" timestamp with time zone,
    "p_replacement_rows" jsonb
) RETURNS TABLE("deleted_count" bigint, "replaced_count" bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path TO ''
AS $$
DECLARE v_deleted bigint; v_replaced bigint;
BEGIN
  IF p_symbol IS NULL OR btrim(p_symbol) = '' OR upper(btrim(p_symbol)) IN ('*','%','ALL') OR p_symbol ~ '[*,%]' THEN
    RAISE EXCEPTION 'replace_features_atomic requires one exact symbol';
  END IF;
  IF p_timeframe NOT IN ('1d','15m','60m') THEN RAISE EXCEPTION 'invalid persisted timeframe'; END IF;
  IF p_start_utc IS NULL OR p_end_exclusive_utc IS NULL OR p_start_utc >= p_end_exclusive_utc THEN RAISE EXCEPTION 'invalid half-open UTC range'; END IF;
  IF p_replacement_rows IS NULL OR jsonb_typeof(p_replacement_rows) <> 'array' OR jsonb_array_length(p_replacement_rows) = 0 THEN RAISE EXCEPTION 'empty replacement dataset'; END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_replacement_rows) r WHERE r->>'symbol' IS DISTINCT FROM p_symbol OR r->>'timeframe' IS DISTINCT FROM p_timeframe OR nullif(r->>'time','') IS NULL OR (r->>'time')::timestamptz < p_start_utc OR (r->>'time')::timestamptz >= p_end_exclusive_utc) THEN RAISE EXCEPTION 'replacement row outside scope'; END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_replacement_rows) r GROUP BY r->>'symbol',r->>'timeframe',(r->>'time')::timestamptz HAVING count(*) > 1) THEN RAISE EXCEPTION 'duplicate replacement key'; END IF;
  DELETE FROM public.stock_features WHERE symbol=p_symbol AND timeframe=p_timeframe AND time>=p_start_utc AND time<p_end_exclusive_utc;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  INSERT INTO public.stock_features SELECT x.* FROM jsonb_populate_recordset(NULL::public.stock_features,p_replacement_rows) x;
  GET DIAGNOSTICS v_replaced = ROW_COUNT;
  IF v_replaced <> jsonb_array_length(p_replacement_rows) THEN RAISE EXCEPTION 'replacement count mismatch'; END IF;
  RETURN QUERY SELECT v_deleted,v_replaced;
END $$;
REVOKE ALL ON FUNCTION "public"."replace_features_atomic"(text,text,timestamptz,timestamptz,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION "public"."replace_features_atomic"(text,text,timestamptz,timestamptz,jsonb) TO service_role;


CREATE TABLE IF NOT EXISTS "public"."stock_foreign_trading" (
    "symbol" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "buy_vol" bigint,
    "sell_vol" bigint,
    "net_vol" bigint
);


ALTER TABLE "public"."stock_foreign_trading" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_orderbook_snapshot" (
    "id" bigint NOT NULL,
    "symbol" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "bid_price_1" double precision,
    "bid_vol_1" bigint,
    "bid_price_2" double precision,
    "bid_vol_2" bigint,
    "bid_price_3" double precision,
    "bid_vol_3" bigint,
    "bid_price_4" double precision,
    "bid_vol_4" bigint,
    "bid_price_5" double precision,
    "bid_vol_5" bigint,
    "bid_price_6" double precision,
    "bid_vol_6" bigint,
    "bid_price_7" double precision,
    "bid_vol_7" bigint,
    "bid_price_8" double precision,
    "bid_vol_8" bigint,
    "bid_price_9" double precision,
    "bid_vol_9" bigint,
    "bid_price_10" double precision,
    "bid_vol_10" bigint,
    "ask_price_1" double precision,
    "ask_vol_1" bigint,
    "ask_price_2" double precision,
    "ask_vol_2" bigint,
    "ask_price_3" double precision,
    "ask_vol_3" bigint,
    "ask_price_4" double precision,
    "ask_vol_4" bigint,
    "ask_price_5" double precision,
    "ask_vol_5" bigint,
    "ask_price_6" double precision,
    "ask_vol_6" bigint,
    "ask_price_7" double precision,
    "ask_vol_7" bigint,
    "ask_price_8" double precision,
    "ask_vol_8" bigint,
    "ask_price_9" double precision,
    "ask_vol_9" bigint,
    "ask_price_10" double precision,
    "ask_vol_10" bigint,
    "total_bid_depth_10" bigint,
    "total_ask_depth_10" bigint,
    "orderbook_imbalance" double precision,
    "pressure_score" double precision
);


ALTER TABLE "public"."stock_orderbook_snapshot" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."stock_orderbook_snapshot_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."stock_orderbook_snapshot_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."stock_orderbook_snapshot_id_seq" OWNED BY "public"."stock_orderbook_snapshot"."id";



CREATE TABLE IF NOT EXISTS "public"."stock_raw_intraday" (
    "id" bigint NOT NULL,
    "symbol" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "data_hash" "text",
    "payload" jsonb,
    "source" "text" DEFAULT 'SSI'::"text",
    "fetched_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_raw_intraday" OWNER TO "postgres";

COMMENT ON COLUMN "public"."stock_raw_intraday"."payload" IS 'Original semantic SSI candle JSON object; historical rows may be NULL.';


CREATE SEQUENCE IF NOT EXISTS "public"."stock_raw_intraday_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."stock_raw_intraday_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."stock_raw_intraday_id_seq" OWNED BY "public"."stock_raw_intraday"."id";



CREATE TABLE IF NOT EXISTS "public"."stock_intraday" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
)
PARTITION BY RANGE ("time");


ALTER TABLE "public"."stock_intraday" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_01" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_01" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_02" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_02" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_03" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_03" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_04" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_04" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_05" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_05" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_06" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_06" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_07" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_07" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_08" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_08" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_09" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_09" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_10" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_10" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_11" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_11" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2023_12" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2023_12" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_01" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_01" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_02" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_02" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_03" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_03" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_04" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_04" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_05" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_05" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_06" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_06" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_07" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_07" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_08" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_08" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_09" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_09" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_10" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_10" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_11" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_11" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2024_12" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2024_12" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_01" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_01" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_02" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_02" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_03" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_03" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_04" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_04" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_05" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_05" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_06" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_06" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_07" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_07" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_08" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_08" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_09" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_09" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_10" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_10" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_11" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_11" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2025_12" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2025_12" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_01" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_01" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_02" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_02" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_03" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_03" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_04" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_04" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_05" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_05" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_06" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_06" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_07" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_07" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_08" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_08" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_09" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_09" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_10" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_10" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_11" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_11" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stock_intraday_2026_12" (
    "symbol" "text" NOT NULL,
    "timeframe" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "open" double precision,
    "high" double precision,
    "low" double precision,
    "close" double precision,
    "volume" bigint,
    "value" bigint,
    "volume_delta" bigint,
    "reference_price" double precision,
    "ceiling_price" double precision,
    "floor_price" double precision,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."stock_intraday_2026_12" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."symbols" (
    "symbol" "text" NOT NULL,
    "market" "text",
    "name" "text",
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "intraday_status" "text" DEFAULT 'inactive'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "symbols_status_check" CHECK ("status" IN ('active', 'inactive')),
    CONSTRAINT "symbols_intraday_status_check" CHECK ("intraday_status" IN ('active', 'inactive'))
);


ALTER TABLE "public"."symbols" OWNER TO "postgres";



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_01" FOR VALUES FROM ('2023-01-01 00:00:00+00') TO ('2023-02-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_02" FOR VALUES FROM ('2023-02-01 00:00:00+00') TO ('2023-03-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_03" FOR VALUES FROM ('2023-03-01 00:00:00+00') TO ('2023-04-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_04" FOR VALUES FROM ('2023-04-01 00:00:00+00') TO ('2023-05-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_05" FOR VALUES FROM ('2023-05-01 00:00:00+00') TO ('2023-06-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_06" FOR VALUES FROM ('2023-06-01 00:00:00+00') TO ('2023-07-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_07" FOR VALUES FROM ('2023-07-01 00:00:00+00') TO ('2023-08-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_08" FOR VALUES FROM ('2023-08-01 00:00:00+00') TO ('2023-09-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_09" FOR VALUES FROM ('2023-09-01 00:00:00+00') TO ('2023-10-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_10" FOR VALUES FROM ('2023-10-01 00:00:00+00') TO ('2023-11-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_11" FOR VALUES FROM ('2023-11-01 00:00:00+00') TO ('2023-12-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2023_12" FOR VALUES FROM ('2023-12-01 00:00:00+00') TO ('2024-01-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_01" FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2024-02-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_02" FOR VALUES FROM ('2024-02-01 00:00:00+00') TO ('2024-03-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_03" FOR VALUES FROM ('2024-03-01 00:00:00+00') TO ('2024-04-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_04" FOR VALUES FROM ('2024-04-01 00:00:00+00') TO ('2024-05-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_05" FOR VALUES FROM ('2024-05-01 00:00:00+00') TO ('2024-06-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_06" FOR VALUES FROM ('2024-06-01 00:00:00+00') TO ('2024-07-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_07" FOR VALUES FROM ('2024-07-01 00:00:00+00') TO ('2024-08-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_08" FOR VALUES FROM ('2024-08-01 00:00:00+00') TO ('2024-09-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_09" FOR VALUES FROM ('2024-09-01 00:00:00+00') TO ('2024-10-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_10" FOR VALUES FROM ('2024-10-01 00:00:00+00') TO ('2024-11-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_11" FOR VALUES FROM ('2024-11-01 00:00:00+00') TO ('2024-12-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2024_12" FOR VALUES FROM ('2024-12-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_01" FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_02" FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_03" FOR VALUES FROM ('2025-03-01 00:00:00+00') TO ('2025-04-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_04" FOR VALUES FROM ('2025-04-01 00:00:00+00') TO ('2025-05-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_05" FOR VALUES FROM ('2025-05-01 00:00:00+00') TO ('2025-06-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_06" FOR VALUES FROM ('2025-06-01 00:00:00+00') TO ('2025-07-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_07" FOR VALUES FROM ('2025-07-01 00:00:00+00') TO ('2025-08-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_08" FOR VALUES FROM ('2025-08-01 00:00:00+00') TO ('2025-09-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_09" FOR VALUES FROM ('2025-09-01 00:00:00+00') TO ('2025-10-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_10" FOR VALUES FROM ('2025-10-01 00:00:00+00') TO ('2025-11-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_11" FOR VALUES FROM ('2025-11-01 00:00:00+00') TO ('2025-12-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2025_12" FOR VALUES FROM ('2025-12-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_01" FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_02" FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_03" FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_04" FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-05-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_05" FOR VALUES FROM ('2026-05-01 00:00:00+00') TO ('2026-06-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_06" FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_07" FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_08" FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_09" FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_10" FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_11" FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_intraday" ATTACH PARTITION "public"."stock_intraday_2026_12" FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');



ALTER TABLE ONLY "public"."stock_orderbook_snapshot" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."stock_orderbook_snapshot_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."stock_raw_intraday" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."stock_raw_intraday_id_seq"'::"regclass");







ALTER TABLE ONLY "public"."stock_features"
    ADD CONSTRAINT "stock_features_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_foreign_trading"
    ADD CONSTRAINT "stock_foreign_trading_pkey" PRIMARY KEY ("symbol", "time");



ALTER TABLE ONLY "public"."stock_orderbook_snapshot"
    ADD CONSTRAINT "stock_orderbook_snapshot_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."stock_raw_intraday"
    ADD CONSTRAINT "stock_raw_intraday_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."stock_intraday"
    ADD CONSTRAINT "stock_intraday_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_01"
    ADD CONSTRAINT "stock_intraday_2023_01_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_02"
    ADD CONSTRAINT "stock_intraday_2023_02_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_03"
    ADD CONSTRAINT "stock_intraday_2023_03_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_04"
    ADD CONSTRAINT "stock_intraday_2023_04_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_05"
    ADD CONSTRAINT "stock_intraday_2023_05_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_06"
    ADD CONSTRAINT "stock_intraday_2023_06_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_07"
    ADD CONSTRAINT "stock_intraday_2023_07_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_08"
    ADD CONSTRAINT "stock_intraday_2023_08_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_09"
    ADD CONSTRAINT "stock_intraday_2023_09_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_10"
    ADD CONSTRAINT "stock_intraday_2023_10_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_11"
    ADD CONSTRAINT "stock_intraday_2023_11_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2023_12"
    ADD CONSTRAINT "stock_intraday_2023_12_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_01"
    ADD CONSTRAINT "stock_intraday_2024_01_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_02"
    ADD CONSTRAINT "stock_intraday_2024_02_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_03"
    ADD CONSTRAINT "stock_intraday_2024_03_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_04"
    ADD CONSTRAINT "stock_intraday_2024_04_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_05"
    ADD CONSTRAINT "stock_intraday_2024_05_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_06"
    ADD CONSTRAINT "stock_intraday_2024_06_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_07"
    ADD CONSTRAINT "stock_intraday_2024_07_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_08"
    ADD CONSTRAINT "stock_intraday_2024_08_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_09"
    ADD CONSTRAINT "stock_intraday_2024_09_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_10"
    ADD CONSTRAINT "stock_intraday_2024_10_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_11"
    ADD CONSTRAINT "stock_intraday_2024_11_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2024_12"
    ADD CONSTRAINT "stock_intraday_2024_12_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_01"
    ADD CONSTRAINT "stock_intraday_2025_01_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_02"
    ADD CONSTRAINT "stock_intraday_2025_02_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_03"
    ADD CONSTRAINT "stock_intraday_2025_03_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_04"
    ADD CONSTRAINT "stock_intraday_2025_04_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_05"
    ADD CONSTRAINT "stock_intraday_2025_05_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_06"
    ADD CONSTRAINT "stock_intraday_2025_06_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_07"
    ADD CONSTRAINT "stock_intraday_2025_07_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_08"
    ADD CONSTRAINT "stock_intraday_2025_08_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_09"
    ADD CONSTRAINT "stock_intraday_2025_09_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_10"
    ADD CONSTRAINT "stock_intraday_2025_10_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_11"
    ADD CONSTRAINT "stock_intraday_2025_11_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2025_12"
    ADD CONSTRAINT "stock_intraday_2025_12_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_01"
    ADD CONSTRAINT "stock_intraday_2026_01_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_02"
    ADD CONSTRAINT "stock_intraday_2026_02_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_03"
    ADD CONSTRAINT "stock_intraday_2026_03_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_04"
    ADD CONSTRAINT "stock_intraday_2026_04_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_05"
    ADD CONSTRAINT "stock_intraday_2026_05_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_06"
    ADD CONSTRAINT "stock_intraday_2026_06_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_07"
    ADD CONSTRAINT "stock_intraday_2026_07_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_08"
    ADD CONSTRAINT "stock_intraday_2026_08_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_09"
    ADD CONSTRAINT "stock_intraday_2026_09_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_10"
    ADD CONSTRAINT "stock_intraday_2026_10_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_11"
    ADD CONSTRAINT "stock_intraday_2026_11_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."stock_intraday_2026_12"
    ADD CONSTRAINT "stock_intraday_2026_12_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."symbols"
    ADD CONSTRAINT "symbols_pkey" PRIMARY KEY ("symbol");











CREATE INDEX "idx_stock_features_symbol_time" ON "public"."stock_features" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "idx_foreign_symbol_time" ON "public"."stock_foreign_trading" USING "btree" ("symbol", "time" DESC);



CREATE INDEX "idx_intraday_symbol_time" ON ONLY "public"."stock_intraday" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "idx_orderbook_symbol_time" ON "public"."stock_orderbook_snapshot" USING "btree" ("symbol", "time" DESC);



CREATE INDEX "idx_orderbook_time" ON "public"."stock_orderbook_snapshot" USING "btree" ("time" DESC);



CREATE INDEX "idx_raw_fetched" ON "public"."stock_raw_intraday" USING "btree" ("fetched_at" DESC);



CREATE INDEX "idx_raw_symbol_time" ON "public"."stock_raw_intraday" USING "btree" ("symbol", "time" DESC);



CREATE UNIQUE INDEX "stock_raw_intraday_symbol_time_data_hash_uidx" ON "public"."stock_raw_intraday" USING "btree" ("symbol", "time", "data_hash");



CREATE INDEX "stock_intraday_2023_01_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_01" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_02_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_02" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_03_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_03" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_04_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_04" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_05_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_05" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_06_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_06" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_07_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_07" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_08_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_08" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_09_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_09" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_10_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_10" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_11_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_11" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2023_12_symbol_timeframe_time_idx" ON "public"."stock_intraday_2023_12" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_01_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_01" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_02_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_02" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_03_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_03" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_04_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_04" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_05_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_05" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_06_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_06" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_07_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_07" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_08_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_08" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_09_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_09" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_10_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_10" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_11_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_11" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2024_12_symbol_timeframe_time_idx" ON "public"."stock_intraday_2024_12" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_01_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_01" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_02_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_02" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_03_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_03" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_04_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_04" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_05_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_05" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_06_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_06" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_07_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_07" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_08_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_08" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_09_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_09" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_10_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_10" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_11_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_11" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2025_12_symbol_timeframe_time_idx" ON "public"."stock_intraday_2025_12" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_01_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_01" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_02_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_02" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_03_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_03" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_04_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_04" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_05_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_05" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_06_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_06" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_07_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_07" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_08_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_08" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_09_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_09" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_10_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_10" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_11_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_11" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "stock_intraday_2026_12_symbol_timeframe_time_idx" ON "public"."stock_intraday_2026_12" USING "btree" ("symbol", "timeframe", "time" DESC);



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_01_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_01_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_02_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_02_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_03_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_03_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_04_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_04_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_05_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_05_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_06_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_06_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_07_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_07_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_08_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_08_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_09_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_09_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_10_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_10_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_11_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_11_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2023_12_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2023_12_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_01_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_01_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_02_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_02_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_03_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_03_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_04_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_04_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_05_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_05_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_06_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_06_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_07_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_07_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_08_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_08_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_09_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_09_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_10_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_10_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_11_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_11_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2024_12_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2024_12_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_01_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_01_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_02_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_02_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_03_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_03_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_04_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_04_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_05_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_05_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_06_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_06_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_07_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_07_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_08_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_08_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_09_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_09_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_10_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_10_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_11_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_11_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2025_12_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2025_12_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_01_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_01_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_02_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_02_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_03_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_03_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_04_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_04_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_05_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_05_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_06_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_06_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_07_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_07_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_08_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_08_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_09_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_09_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_10_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_10_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_11_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_11_symbol_timeframe_time_idx";



ALTER INDEX "public"."stock_intraday_pkey" ATTACH PARTITION "public"."stock_intraday_2026_12_pkey";



ALTER INDEX "public"."idx_intraday_symbol_time" ATTACH PARTITION "public"."stock_intraday_2026_12_symbol_timeframe_time_idx";





ALTER TABLE ONLY "public"."stock_features"
    ADD CONSTRAINT "stock_features_symbol_fkey" FOREIGN KEY ("symbol") REFERENCES "public"."symbols"("symbol");



ALTER TABLE ONLY "public"."stock_foreign_trading"
    ADD CONSTRAINT "stock_foreign_trading_symbol_fkey" FOREIGN KEY ("symbol") REFERENCES "public"."symbols"("symbol");



ALTER TABLE "public"."stock_intraday"
    ADD CONSTRAINT "stock_intraday_symbol_fkey" FOREIGN KEY ("symbol") REFERENCES "public"."symbols"("symbol");





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";






















































































































































GRANT ALL ON FUNCTION "public"."check_data_freshness"("p_symbol" "text", "p_max_lag_minutes" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."check_data_freshness"("p_symbol" "text", "p_max_lag_minutes" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."check_data_freshness"("p_symbol" "text", "p_max_lag_minutes" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."cleanup_old_orderbook"("days" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."cleanup_old_orderbook"("days" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."cleanup_old_orderbook"("days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."cleanup_old_raw_data"() TO "anon";
GRANT ALL ON FUNCTION "public"."cleanup_old_raw_data"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."cleanup_old_raw_data"() TO "service_role";



GRANT ALL ON FUNCTION "public"."create_partition_if_not_exists"("p_table" "text", "p_time" timestamp with time zone) TO "anon";
GRANT ALL ON FUNCTION "public"."create_partition_if_not_exists"("p_table" "text", "p_time" timestamp with time zone) TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_partition_if_not_exists"("p_table" "text", "p_time" timestamp with time zone) TO "service_role";



















GRANT ALL ON TABLE "public"."stock_features" TO "anon";
GRANT ALL ON TABLE "public"."stock_features" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_features" TO "service_role";



GRANT ALL ON TABLE "public"."stock_foreign_trading" TO "anon";
GRANT ALL ON TABLE "public"."stock_foreign_trading" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_foreign_trading" TO "service_role";



GRANT ALL ON TABLE "public"."stock_orderbook_snapshot" TO "anon";
GRANT ALL ON TABLE "public"."stock_orderbook_snapshot" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_orderbook_snapshot" TO "service_role";



GRANT ALL ON SEQUENCE "public"."stock_orderbook_snapshot_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."stock_orderbook_snapshot_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."stock_orderbook_snapshot_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."stock_raw_intraday" TO "anon";
GRANT ALL ON TABLE "public"."stock_raw_intraday" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_raw_intraday" TO "service_role";



GRANT ALL ON SEQUENCE "public"."stock_raw_intraday_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."stock_raw_intraday_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."stock_raw_intraday_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_01" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_01" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_01" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_02" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_02" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_02" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_03" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_03" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_03" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_04" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_04" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_04" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_05" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_05" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_05" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_06" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_06" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_06" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_07" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_07" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_07" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_08" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_08" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_08" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_09" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_09" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_09" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_10" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_10" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_10" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_11" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_11" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_11" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2023_12" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2023_12" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2023_12" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_01" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_01" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_01" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_02" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_02" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_02" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_03" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_03" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_03" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_04" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_04" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_04" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_05" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_05" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_05" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_06" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_06" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_06" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_07" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_07" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_07" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_08" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_08" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_08" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_09" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_09" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_09" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_10" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_10" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_10" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_11" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_11" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_11" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2024_12" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2024_12" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2024_12" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_01" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_01" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_01" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_02" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_02" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_02" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_03" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_03" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_03" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_04" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_04" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_04" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_05" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_05" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_05" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_06" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_06" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_06" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_07" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_07" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_07" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_08" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_08" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_08" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_09" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_09" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_09" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_10" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_10" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_10" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_11" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_11" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_11" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2025_12" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2025_12" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2025_12" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_01" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_01" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_01" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_02" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_02" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_02" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_03" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_03" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_03" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_04" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_04" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_04" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_05" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_05" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_05" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_06" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_06" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_06" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_07" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_07" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_07" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_08" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_08" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_08" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_09" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_09" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_09" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_10" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_10" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_10" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_11" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_11" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_11" TO "service_role";



GRANT ALL ON TABLE "public"."stock_intraday_2026_12" TO "anon";
GRANT ALL ON TABLE "public"."stock_intraday_2026_12" TO "authenticated";
GRANT ALL ON TABLE "public"."stock_intraday_2026_12" TO "service_role";



GRANT ALL ON TABLE "public"."symbols" TO "anon";
GRANT ALL ON TABLE "public"."symbols" TO "authenticated";
GRANT ALL ON TABLE "public"."symbols" TO "service_role";














-- Foreign EOD Feature V1 (migration 20260907).
-- Additive Foreign EOD Feature V1 storage and shared read-only report RPCs.


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


ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";
































-- Streaming ingest reconciliation snapshot (Issue #73).
-- See migrations/20260717_reconcile_streaming_ingest.sql for idempotent production DDL.
