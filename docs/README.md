# Project documentation

## Exact daily numerics — 4 November 2026

Daily mapping/contract 3.0.0 uses Decimal for money/prices/levels/percentages and
exact integers for discrete quantities. Stock policy 1.1.0 preserves monetary
fractions with FRACTIONAL_MONETARY_VALUE/PARTIAL; Index keeps its separate pipeline
and rejects invalid numerics. Owner must apply **new migration**
`20261104_daily_numeric_precision.sql`; the applied V1 migration is unchanged.
No automatic historical rewrite/backfill/features. Read-only diagnostic:
`python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(use dataset index_daily/identifiers VNINDEX for Index).
[Field matrix, transport, audit, SQL/deployment/rollback and owner commands](DAILY_NUMERIC_PRECISION.md).
This supersedes earlier daily integer-money/float instructions; prior test observations remain historical evidence.


## Stock Daily Data Quality V1 — 3 November 2026

SSI v3 Stock Daily now uses VALID/PARTIAL/REJECTED, field-level NULL quarantine,
immutable RAW and current/history issue evidence. Owner must apply
`20261103_stock_daily_quality_v1.sql` before new writers; historical status stays NULL.
New read-only diagnostic: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Existing `stock-eod`/`stock-eod-backfill` names remain; no automatic backfill/features.
[Policy, deployment, verification SQL and scoped rerun](STOCK_DAILY_QUALITY_V1.md).


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
| [`phase1/`](phase1/README.md) | Implemented same-symbol Historical Analog EOD V1 contract and cleanup status. |

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

- [Historical Analog Core EOD V1](../src/research/analogs/README.md) — implemented
  same-symbol EOD backend foundation; draft/null-threshold production gate.
