


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
    DELETE FROM orderbook_snapshot WHERE time < NOW() - (days || ' days')::INTERVAL;
    RAISE NOTICE 'Cleaned orderbook data older than % days', days;
END;
$$;


ALTER FUNCTION "public"."cleanup_old_orderbook"("days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."cleanup_old_raw_data"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    DELETE FROM raw_intraday WHERE fetched_at < NOW() - INTERVAL '1095 days';
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

CREATE TABLE IF NOT EXISTS "public"."index_master" (
    "index_code" text NOT NULL PRIMARY KEY, "index_name" text, "exchange" text,
    "raw" jsonb, "updated_at" timestamp with time zone
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


CREATE TABLE IF NOT EXISTS "public"."features" (
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


ALTER TABLE "public"."features" OWNER TO "postgres";

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
  DELETE FROM public.features WHERE symbol=p_symbol AND timeframe=p_timeframe AND time>=p_start_utc AND time<p_end_exclusive_utc;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  INSERT INTO public.features SELECT x.* FROM jsonb_populate_recordset(NULL::public.features,p_replacement_rows) x;
  GET DIAGNOSTICS v_replaced = ROW_COUNT;
  IF v_replaced <> jsonb_array_length(p_replacement_rows) THEN RAISE EXCEPTION 'replacement count mismatch'; END IF;
  RETURN QUERY SELECT v_deleted,v_replaced;
END $$;
REVOKE ALL ON FUNCTION "public"."replace_features_atomic"(text,text,timestamptz,timestamptz,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION "public"."replace_features_atomic"(text,text,timestamptz,timestamptz,jsonb) TO service_role;


CREATE TABLE IF NOT EXISTS "public"."foreign_trading" (
    "symbol" "text" NOT NULL,
    "time" timestamp with time zone NOT NULL,
    "buy_vol" bigint,
    "sell_vol" bigint,
    "net_vol" bigint
);


ALTER TABLE "public"."foreign_trading" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."orderbook_snapshot" (
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


ALTER TABLE "public"."orderbook_snapshot" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."orderbook_snapshot_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."orderbook_snapshot_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."orderbook_snapshot_id_seq" OWNED BY "public"."orderbook_snapshot"."id";



CREATE TABLE IF NOT EXISTS "public"."raw_intraday" (
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


ALTER TABLE "public"."raw_intraday" OWNER TO "postgres";

COMMENT ON COLUMN "public"."raw_intraday"."payload" IS 'Original semantic SSI candle JSON object; historical rows may be NULL.';


CREATE SEQUENCE IF NOT EXISTS "public"."raw_intraday_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."raw_intraday_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."raw_intraday_id_seq" OWNED BY "public"."raw_intraday"."id";



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
    "created_at" timestamp with time zone DEFAULT "now"()
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



ALTER TABLE ONLY "public"."orderbook_snapshot" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."orderbook_snapshot_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."raw_intraday" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."raw_intraday_id_seq"'::"regclass");







ALTER TABLE ONLY "public"."features"
    ADD CONSTRAINT "features_pkey" PRIMARY KEY ("symbol", "timeframe", "time");



ALTER TABLE ONLY "public"."foreign_trading"
    ADD CONSTRAINT "foreign_trading_pkey" PRIMARY KEY ("symbol", "time");



ALTER TABLE ONLY "public"."orderbook_snapshot"
    ADD CONSTRAINT "orderbook_snapshot_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."raw_intraday"
    ADD CONSTRAINT "raw_intraday_pkey" PRIMARY KEY ("id");



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











CREATE INDEX "idx_features_symbol_time" ON "public"."features" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "idx_foreign_symbol_time" ON "public"."foreign_trading" USING "btree" ("symbol", "time" DESC);



CREATE INDEX "idx_intraday_symbol_time" ON ONLY "public"."stock_intraday" USING "btree" ("symbol", "timeframe", "time" DESC);



CREATE INDEX "idx_orderbook_symbol_time" ON "public"."orderbook_snapshot" USING "btree" ("symbol", "time" DESC);



CREATE INDEX "idx_orderbook_time" ON "public"."orderbook_snapshot" USING "btree" ("time" DESC);



CREATE INDEX "idx_raw_fetched" ON "public"."raw_intraday" USING "btree" ("fetched_at" DESC);



CREATE INDEX "idx_raw_symbol_time" ON "public"."raw_intraday" USING "btree" ("symbol", "time" DESC);



CREATE UNIQUE INDEX "raw_intraday_symbol_time_data_hash_uidx" ON "public"."raw_intraday" USING "btree" ("symbol", "time", "data_hash");



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





ALTER TABLE ONLY "public"."features"
    ADD CONSTRAINT "features_symbol_fkey" FOREIGN KEY ("symbol") REFERENCES "public"."symbols"("symbol");



ALTER TABLE ONLY "public"."foreign_trading"
    ADD CONSTRAINT "foreign_trading_symbol_fkey" FOREIGN KEY ("symbol") REFERENCES "public"."symbols"("symbol");



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



















GRANT ALL ON TABLE "public"."features" TO "anon";
GRANT ALL ON TABLE "public"."features" TO "authenticated";
GRANT ALL ON TABLE "public"."features" TO "service_role";



GRANT ALL ON TABLE "public"."foreign_trading" TO "anon";
GRANT ALL ON TABLE "public"."foreign_trading" TO "authenticated";
GRANT ALL ON TABLE "public"."foreign_trading" TO "service_role";



GRANT ALL ON TABLE "public"."orderbook_snapshot" TO "anon";
GRANT ALL ON TABLE "public"."orderbook_snapshot" TO "authenticated";
GRANT ALL ON TABLE "public"."orderbook_snapshot" TO "service_role";



GRANT ALL ON SEQUENCE "public"."orderbook_snapshot_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."orderbook_snapshot_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."orderbook_snapshot_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."raw_intraday" TO "anon";
GRANT ALL ON TABLE "public"."raw_intraday" TO "authenticated";
GRANT ALL ON TABLE "public"."raw_intraday" TO "service_role";



GRANT ALL ON SEQUENCE "public"."raw_intraday_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."raw_intraday_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."raw_intraday_id_seq" TO "service_role";



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
