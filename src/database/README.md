# Database access

Supabase client and repository persistence helpers.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Main files

- `client.py`: initializes the Supabase client and exposes table-specific read/insert/upsert helpers.
- `__init__.py`: package exports.

## Responsibilities

- Read master, raw, clean, feature, and snapshot data required by current pipelines.
- Persist records using documented table and conflict-key contracts.
- Propagate useful errors instead of silently swallowing database failures.
- Keep credentials in environment variables and never print them.

## Boundaries

- This package does not define or migrate the database schema.
- Schema changes belong in [`migrations/`](../../migrations/README.md).
- Before adding an `upsert`, verify that the matching unique index exists.
- Do not fall back to duplicate-producing writes merely to keep a job running.
- Do not convert missing market fields into zero unless a verified rule requires it.

## Testing

Use mocked Supabase clients for unit tests. Live smoke checks should be read-only by default and run through scripts such as `scripts/check_supabase.py` and `scripts/check_ssi_ingest_schema.py`.

## Phase 1 adapter
The retired rule-based database adapter has been removed. Historical Analog uses
its dedicated repository and seven-table migration without writing raw, clean,
or feature tables.
