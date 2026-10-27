-- Stage B: OPTIONAL OWNER-ONLY, never run in an automatic migration batch.
-- Stage A -> deploy unified application -> owner verification/smokes -> backups -> approval.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $approval$
BEGIN
 IF current_setting('app.approve_retire_securities',true) IS DISTINCT FROM 'owner-reviewed-and-backed-up' THEN
  RAISE EXCEPTION 'Stage B requires explicit owner approval after dependency, coverage and backup verification';
 END IF;
 IF EXISTS (SELECT 1 FROM public.securities s LEFT JOIN public.symbols t USING(symbol) WHERE t.symbol IS NULL) THEN
  RAISE EXCEPTION 'Unmigrated legacy identities remain';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_proc WHERE pronamespace='public'::regnamespace AND prosrc ~ '\msecurities\M') THEN
  RAISE EXCEPTION 'Stored function still references securities';
 END IF;
END $approval$;
-- No CASCADE: dependent views/FKs/triggers prevent drop. Inspect dynamic SQL,
-- external applications and scheduler jobs manually; catalog dependency tracking
-- cannot prove absence of dynamic/external consumers.
DROP TABLE public.securities RESTRICT;
COMMIT;
-- Before execution owner must inspect pg_depend, pg_views, pg_matviews, pg_proc,
-- information_schema.triggers, pg_constraint, cron.job (if installed), all clients/jobs.
-- Restore legacy table/data/grants/indexes from verified backup for rollback.
