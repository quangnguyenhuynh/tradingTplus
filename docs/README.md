# Project documentation

Repository-level product, architecture, state, CLI, and database documentation.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Main documents

| File | Purpose |
| --- | --- |
| `PROJECT_OVERVIEW.md` | Product goal, Phase 0 priorities, use cases, and component overview. |
| `CURRENT_STATE.md` | Point-in-time implementation assessment and known gaps; reviewed against code on 18/07/2026. |
| `DATA_PIPELINE.md` | Current separation of master, daily, intraday, streaming, validation, and feature flows. |
| `ARCHITECTURE_DECISIONS.md` | Accepted pipeline and data-contract decisions. |
| `CLI_USAGE.md` | Production and operational command reference. |
| `DATA_CONVENTIONS.md` / `DATA_CONVENTIONS.vi.md` | English/Vietnamese timestamp, session, missing-data, unit, and provenance rules. |
| [`backfill/`](backfill/README.md) | Source-data backfill behavior, safety, and commands. |
| [`phase1/`](phase1/README.md) | Proposed rule, backtest, and approval contracts for the new downstream research layer. |

The executable database contract is [`../schema.sql`](../schema.sql), with change
history and deployment SQL documented under [`../migrations/`](../migrations/README.md).

## Documentation rules

- Describe current executable behavior separately from future proposals.
- Verify statements against code, schema, migrations, and tests.
- Include an explicit review date in point-in-time status documents.
- Do not describe research/MVP signal or backtest code as validated production behavior.
- Do not infer that a migration is deployed merely because it exists in the repository.
- When documents conflict, current executable code, schema, migrations, tests, and `AGENTS.md` take precedence.

## Maintenance

Re-review point-in-time documents whenever production behavior changes. Treat
their embedded review dates as assessment dates, not as proof of the deployed
production schema.
