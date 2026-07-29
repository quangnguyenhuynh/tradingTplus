-- Remove feature columns deprecated by the canonical Phase 0 contract.
-- PRE: SELECT column_name FROM information_schema.columns
--      WHERE table_schema='public' AND table_name='features' ORDER BY ordinal_position;
-- PRE: inspect pg_depend for dependencies. Drops below are deliberately restrictive;
--      deployment must stop rather than remove an unknown dependent object.
ALTER TABLE public.features
    DROP COLUMN IF EXISTS rsi,
    DROP COLUMN IF EXISTS atr,
    DROP COLUMN IF EXISTS ema_20,
    DROP COLUMN IF EXISTS ema_50,
    DROP COLUMN IF EXISTS vwap,
    DROP COLUMN IF EXISTS bb_upper,
    DROP COLUMN IF EXISTS bb_lower,
    DROP COLUMN IF EXISTS volume_spike;

-- POST: verify all 35 canonical value columns plus symbol, timeframe, time and
-- last_updated_at; verify the (symbol,timeframe,time) key and existing indexes:
-- SELECT column_name FROM information_schema.columns
--  WHERE table_schema='public' AND table_name='features' ORDER BY ordinal_position;
-- SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='features';
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conrelid='public.features'::regclass;
-- Recovery: restore schema with explicit ADD COLUMN statements. Dropped historical
-- values require a database backup or deterministic feature recomputation; this
-- migration intentionally contains no lossy automatic rollback and never uses CASCADE.
