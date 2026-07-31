-- Remove the retired Phase 0 signal/backtest MVP storage.
--
-- DATA-LOSS WARNING:
-- Applying this migration permanently deletes every row in these two legacy
-- tables. Export any rows required for audit before deployment. The tables are
-- not sources for raw, clean, or feature data, and no backfill is required.
-- PostgreSQL drops table-owned constraints, indexes, and sequences with the
-- tables. The short ACCESS EXCLUSIVE locks last for the DROP statements.

drop table if exists public.trading_signals;
drop table if exists public.backtest_data;

-- Verification (expect zero rows):
-- select table_name
-- from information_schema.tables
-- where table_schema = 'public'
--   and table_name in ('trading_signals', 'backtest_data');

-- Restoration guidance:
-- There is no automatic rollback because the retired contracts must not be
-- recreated as active schema. Restore an operator-created pre-deployment export
-- into an archival schema if historical rows must be retained.
