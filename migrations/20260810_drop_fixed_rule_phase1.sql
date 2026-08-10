-- Retire the superseded Phase 1 fixed-rule strategy/signal/backtest storage.
-- Apply manually only after exporting any evidence that must be retained.
-- Reverse dependency order avoids CASCADE and limits the destructive scope to
-- the six retired tables. This migration does not touch Phase 0 or Analog data.
drop table if exists public.strategy_reviews;
drop table if exists public.backtest_signals;
drop table if exists public.backtest_runs;
drop table if exists public.signals;
drop table if exists public.strategy_setups;
drop table if exists public.strategies;

-- Verification SQL (expect zero rows):
-- select table_name
-- from information_schema.tables
-- where table_schema = 'public'
--   and table_name in (
--     'strategy_reviews', 'backtest_signals', 'backtest_runs',
--     'signals', 'strategy_setups', 'strategies'
--   )
-- order by table_name;
--
-- Confirm protected layers still exist as appropriate for the deployment:
-- select table_name
-- from information_schema.tables
-- where table_schema = 'public'
--   and table_name in (
--     'raw_daily', 'raw_intraday', 'stock_daily', 'stock_intraday', 'features',
--     'analog_profiles', 'analog_snapshots', 'analog_outcomes',
--     'analog_validation_runs', 'analog_profile_reviews', 'analog_queries',
--     'analog_query_matches'
--   )
-- order by table_name;
--
-- Deployment risk: PostgreSQL takes ACCESS EXCLUSIVE locks while dropping each
-- table. Stop retired writers and check dependencies before applying. All rows
-- in these six tables are permanently deleted; export required audit evidence.
-- No source-data, feature, or Analog backfill is required.
--
-- Rollback guidance: there is no data-preserving SQL rollback. To reconstruct
-- empty retired objects, reapply 20260804_create_strategy_signal_backtest.sql
-- followed by 20260806_enforce_phase1_first_match.sql. Restore retained rows
-- only from a verified pre-cleanup export. Application support has been removed,
-- so reconstruction is for exceptional audit recovery, not runtime reactivation.
