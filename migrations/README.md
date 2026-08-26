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
The project owner applied the 20260802 and 20260803 SQL manually through the
Supabase SQL Editor and verified the expected production schema read-only. Their
Phase 0 status is `PASS_WITH_MANUAL_APPLY_NOTE`. Supabase CLI migration history
may omit them; do not rerun or repair them merely to populate history.

## Safety

Never run broad destructive SQL without exact table/date/symbol scope, a verified backup plan, and an explicit task. Do not assume production schema matches the latest repository migration until it is checked.

## 20260826 index_daily primary key

`20260826_add_index_daily_primary_key.sql` promotes the existing unique index on
`(index_code, trading_date)` to `index_daily_pkey`. It fails before alteration if
either key column is null, duplicate key groups exist, the table already has a
primary key, or the expected reusable unique index is missing. It changes no row
values and performs no cleanup/backfill. Apply it manually in a maintenance
window because validating `NOT NULL` and adding the constraint lock
`public.index_daily`.

## Retired signal/backtest storage

`20260731_drop_legacy_signal_backtest.sql` is an explicitly approved cleanup migration. It is destructive only to the retired legacy tables; export their rows before deployment if audit retention is required. It does not affect raw, clean, or feature data, and requires no backfill.

## 20260802_atomic_replace_features.sql
Creates the service-role-only `public.replace_features_atomic(text,text,timestamptz,timestamptz,jsonb)` RPC. It validates an exact symbol, persisted timeframe, half-open UTC range, and non-empty in-scope unique replacement rows before deleting and inserting in one transaction. Applying the migration changes no feature rows. Deploy it before the application code that enables replace. Verification and rollback SQL are included in the migration; rollback drops only the function and does not restore/alter feature rows.
## Retired fixed-rule Phase 1 storage

The `20260804` and `20260806` files are retained only as immutable deployment
history. Do not apply them to new environments.
`20260810_drop_fixed_rule_phase1.sql` drops only their six retired tables in
reverse dependency order. It is manually applied and destructive: export any
required audit evidence first. It requires no source, feature, or Analog backfill.

## 20260809 Historical Analog EOD V1

`20260809_create_historical_analog_core_eod_v1.sql` additively creates the seven
Phase 1 Analog evidence tables. Apply it manually; then run the read-only checks
in `sql/analogs/verify_historical_analog_core_eod_v1.sql`. Cleanup guidance and
lock/data-loss warnings are in `sql/analogs/README.md`.

## 20260811 Historical Analog recovery and runtime RPC

For a fresh installation, apply the corrected `20260809_create_historical_analog_core_eod_v1.sql`. It uses the immutable `analog_jsonb_object_size(jsonb)` helper rather than the unavailable `jsonb_object_length(jsonb)`, while retaining the exact nine-dimension CHECK. If the old 20260809 script stopped part-way, apply `20260811_recover_historical_analog_core_eod_v1.sql` instead (or immediately afterward): it is idempotent, preserves existing Analog rows, completes missing tables/indexes/RLS/grants/policies, and installs the service-role-only `persist_analog_query_v1(jsonb,jsonb)` transactional RPC. Then run the read-only verification SQL. Neither migration changes Phase 0 tables or backfills evidence.
