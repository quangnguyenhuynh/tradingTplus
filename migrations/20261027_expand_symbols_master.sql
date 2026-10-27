-- Stage A: owner/manual only. Backup both tables and pause all master writers.
-- Preflight: SELECT count(*) FROM public.symbols; SELECT count(*) FROM public.securities;
-- Export both tables plus dependent-object definitions BEFORE executing.
BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.symbols, public.securities IN ACCESS EXCLUSIVE MODE;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS stock_en_name text;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS sec_type text;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS exchange text;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS issuer text;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS lot_size numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS listed_share numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS issue_date date;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS first_trading_date date;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS last_trading_date date;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS maturity_date date;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_price1 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_increment1 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_price2 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_increment2 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_price3 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_increment3 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_price4 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS tick_increment4 numeric;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS raw jsonb;
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS updated_at timestamptz;
-- Abort atomically on ANY conflicting non-NULL descriptive value, including raw.
DO $merge$
DECLARE target text; source text; conflicts bigint;
BEGIN
 FOR target,source IN SELECT * FROM (VALUES
('name','stock_name'),
('market','market'),
('stock_en_name','stock_en_name'),
('sec_type','sec_type'),
('exchange','exchange'),
('issuer','issuer'),
('lot_size','lot_size'),
('listed_share','listed_share'),
('issue_date','issue_date'),
('first_trading_date','first_trading_date'),
('last_trading_date','last_trading_date'),
('maturity_date','maturity_date'),
('tick_price1','tick_price1'),
('tick_increment1','tick_increment1'),
('tick_price2','tick_price2'),
('tick_increment2','tick_increment2'),
('tick_price3','tick_price3'),
('tick_increment3','tick_increment3'),
('tick_price4','tick_price4'),
('tick_increment4','tick_increment4'),
('raw','raw')) AS mapping(target,source)
 LOOP
  EXECUTE format('SELECT count(*) FROM public.symbols t JOIN public.securities s USING(symbol) WHERE t.%I IS NOT NULL AND s.%I IS NOT NULL AND t.%I IS DISTINCT FROM s.%I',target,source,target,source) INTO conflicts;
  IF conflicts > 0 THEN RAISE EXCEPTION 'master merge conflicts: column %, rows %. Resolve using backup/preflight; no values overwritten',target,conflicts; END IF;
 END LOOP;
END $merge$;
INSERT INTO public.symbols (symbol,market,name,stock_en_name,sec_type,exchange,issuer,lot_size,listed_share,issue_date,first_trading_date,last_trading_date,maturity_date,tick_price1,tick_increment1,tick_price2,tick_increment2,tick_price3,tick_increment3,tick_price4,tick_increment4,raw,updated_at,status,intraday_status,created_at)
SELECT s.symbol,s.market,s.stock_name,s.stock_en_name,s.sec_type,s.exchange,s.issuer,s.lot_size,s.listed_share,s.issue_date,s.first_trading_date,s.last_trading_date,s.maturity_date,s.tick_price1,s.tick_increment1,s.tick_price2,s.tick_increment2,s.tick_price3,s.tick_increment3,s.tick_price4,s.tick_increment4,s.raw,s.updated_at,'inactive','inactive',NULL FROM public.securities s
ON CONFLICT(symbol) DO UPDATE SET
market=COALESCE(symbols.market,EXCLUDED.market),
name=COALESCE(symbols.name,EXCLUDED.name),
stock_en_name=COALESCE(symbols.stock_en_name,EXCLUDED.stock_en_name),
sec_type=COALESCE(symbols.sec_type,EXCLUDED.sec_type),
exchange=COALESCE(symbols.exchange,EXCLUDED.exchange),
issuer=COALESCE(symbols.issuer,EXCLUDED.issuer),
lot_size=COALESCE(symbols.lot_size,EXCLUDED.lot_size),
listed_share=COALESCE(symbols.listed_share,EXCLUDED.listed_share),
issue_date=COALESCE(symbols.issue_date,EXCLUDED.issue_date),
first_trading_date=COALESCE(symbols.first_trading_date,EXCLUDED.first_trading_date),
last_trading_date=COALESCE(symbols.last_trading_date,EXCLUDED.last_trading_date),
maturity_date=COALESCE(symbols.maturity_date,EXCLUDED.maturity_date),
tick_price1=COALESCE(symbols.tick_price1,EXCLUDED.tick_price1),
tick_increment1=COALESCE(symbols.tick_increment1,EXCLUDED.tick_increment1),
tick_price2=COALESCE(symbols.tick_price2,EXCLUDED.tick_price2),
tick_increment2=COALESCE(symbols.tick_increment2,EXCLUDED.tick_increment2),
tick_price3=COALESCE(symbols.tick_price3,EXCLUDED.tick_price3),
tick_increment3=COALESCE(symbols.tick_increment3,EXCLUDED.tick_increment3),
tick_price4=COALESCE(symbols.tick_price4,EXCLUDED.tick_price4),
tick_increment4=COALESCE(symbols.tick_increment4,EXCLUDED.tick_increment4),
raw=COALESCE(symbols.raw,EXCLUDED.raw),
updated_at=COALESCE(symbols.updated_at,EXCLUDED.updated_at);
COMMIT;
-- Postflight: legacy coverage must be zero missing; compare every descriptive column.
-- SELECT s.symbol FROM public.securities s LEFT JOIN public.symbols t USING(symbol) WHERE t.symbol IS NULL;
-- SELECT status,intraday_status,count(*) FROM public.symbols GROUP BY 1,2;
-- Existing symbols.created_at/status/intraday_status and all referencing FKs stay intact.
-- updated_at: existing target wins, otherwise legacy value; audit timestamps are not source descriptions.
-- Rollback: roll back application first; leave additive columns/rows in place.
-- Never delete new identities with dependent price/feature rows. Restore descriptions
-- only from the preflight backup after scoped review; no destructive automatic rollback.
