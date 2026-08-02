# Database migrations

## 20260803 raw intraday source payload

`20260803_add_raw_intraday_payload.sql` adds nullable `raw_intraday.payload JSONB`
for the complete semantic SSI candle object written by new ingests. Historical
rows remain `NULL`; this migration does not synthesize or backfill payloads and
does not add a GIN index. Use the verification and rollback SQL embedded in the
migration.

Versioned SQL changes for the Trading T+ Supabase/PostgreSQL schema.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Contract

- Every schema change requires a migration.
- Migrations should be additive and idempotent where practical.
- Preserve existing data; do not silently drop, truncate, or reload production tables.
- Create unique indexes required by application `on_conflict` keys.
- Include verification SQL and document backfill, lock, or deployment risk.
- File names follow the existing date-prefixed convention.

## Usage

1. Read `schema.sql`, related migrations, application queries, and tests.
2. Review the migration against the target Supabase schema.
3. Apply it explicitly through the approved deployment process or Supabase SQL editor.
4. Run schema verification and read-only smoke checks.
5. Perform any required backfill as a separate, scoped operation.

Repository migrations are not automatically applied by the Python application.
The 2026-08-02 Phase 0 closure environment had no linked production project or
credentials. Production status of the 20260802 and 20260803 migrations is
therefore `UNKNOWN`; neither was applied or verified by that run.

## Safety

Never run broad destructive SQL without exact table/date/symbol scope, a verified backup plan, and an explicit task. Do not assume production schema matches the latest repository migration until it is checked.

## Retired signal/backtest storage

`20260731_drop_legacy_signal_backtest.sql` is an explicitly approved cleanup migration. It is destructive only to the retired legacy tables; export their rows before deployment if audit retention is required. It does not affect raw, clean, or feature data, and requires no backfill.

## 20260802_atomic_replace_features.sql
Creates the service-role-only `public.replace_features_atomic(text,text,timestamptz,timestamptz,jsonb)` RPC. It validates an exact symbol, persisted timeframe, half-open UTC range, and non-empty in-scope unique replacement rows before deleting and inserting in one transaction. Applying the migration changes no feature rows. Deploy it before the application code that enables replace. Verification and rollback SQL are included in the migration; rollback drops only the function and does not restore/alter feature rows.
