# Project documentation

Repository-level product, architecture, state, CLI, and database documentation.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Main documents

| File | Purpose |
| --- | --- |
| `PROJECT_OVERVIEW.md` | Product goal, Phase 0 priorities, use cases, and component overview. |
| `CURRENT_STATE.md` | Point-in-time implementation assessment and known gaps. |
| `ARCHITECTURE_DECISIONS.md` | Accepted pipeline and data-contract decisions. |
| `CLI_USAGE.md` | Production and operational command reference. |

Additional database notes currently live in the repository root as `docs_db_schema.md`.

## Documentation rules

- Describe current executable behavior separately from future proposals.
- Verify statements against code, schema, migrations, and tests.
- Include an explicit review date in point-in-time status documents.
- Do not describe research/MVP signal or backtest code as validated production behavior.
- Do not infer that a migration is deployed merely because it exists in the repository.

## Known documentation caveat

Some point-in-time documents may become stale as code changes. For example, production `daily` and `intraday-ingest` are separate in current code, while older status text may still combine them. Update the specific status document in a dedicated task when its full content is revalidated.
