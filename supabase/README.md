# Supabase project configuration

Local Supabase CLI configuration for this repository.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Contents

- `config.toml`: Supabase CLI project settings.

Versioned application migrations currently live in the root [`migrations/`](../migrations/README.md) directory, and the reference schema lives in `schema.sql` at the repository root.

## Rules

- Never commit service-role keys, database passwords, access tokens, or generated `.env` files.
- Do not treat local CLI configuration as proof of the deployed production schema.
- Review migration order and target project before linking, pushing, resetting, or applying schema changes.
- Destructive Supabase commands require an explicit task, backup/rollback plan, and impact review.

Use read-only schema checks before any scoped SSI smoke write or backfill.
