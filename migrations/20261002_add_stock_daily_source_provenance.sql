-- Nullable provenance for the provider that last successfully wrote each
-- canonical stock_daily row. Historical provenance is intentionally not
-- fabricated or backfilled.
ALTER TABLE public.stock_daily
ADD COLUMN IF NOT EXISTS source text;

-- Verification:
-- SELECT source, count(*) FROM public.stock_daily GROUP BY source ORDER BY source;
-- Rollback (only before application deployment, if required):
-- ALTER TABLE public.stock_daily DROP COLUMN IF EXISTS source;
