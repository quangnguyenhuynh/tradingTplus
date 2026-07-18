# Operational SQL

Explicit SQL utilities that are not part of the versioned migration chain.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Current content

- `cleanup_accidental_ssi_smoke_records.sql`: cleanup template for narrowly scoped accidental smoke-test rows.

## Safety

Files in this directory may delete or modify data. They must never be executed unchanged against production without reviewing and replacing every scope placeholder.

Before execution:

1. Identify the exact table, symbol, and trading date.
2. Run equivalent `SELECT` statements and record row counts.
3. Use a transaction where practical.
4. Verify affected rows immediately after execution.
5. Keep cleanup separate from migrations and normal ingest/backfill pipelines.

Do not use cleanup SQL as a substitute for fixing idempotency, validation, or incorrect ingest mappings.
