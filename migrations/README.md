# Database migrations

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

## Safety

Never run broad destructive SQL without exact table/date/symbol scope, a verified backup plan, and an explicit task. Do not assume production schema matches the latest repository migration until it is checked.

## Retired signal/backtest storage

`20260731_drop_legacy_signal_backtest.sql` is an explicitly approved cleanup migration. It is destructive only to the retired legacy tables; export their rows before deployment if audit retention is required. It does not affect raw, clean, or feature data, and requires no backfill.
