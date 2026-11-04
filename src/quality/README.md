# src/quality

## Exact daily numerics — 4 November 2026

Daily mapping/contract 3.0.0 uses Decimal for money/prices/levels/percentages and
exact integers for discrete quantities. Stock policy 1.1.0 preserves monetary
fractions with FRACTIONAL_MONETARY_VALUE/PARTIAL; Index keeps its separate pipeline
and rejects invalid numerics. Owner must apply **new migration**
`20261104_daily_numeric_precision.sql`; the applied V1 migration is unchanged.
No automatic historical rewrite/backfill/features. Read-only diagnostic:
`python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(use dataset index_daily/identifiers VNINDEX for Index).
[Field matrix, transport, audit, SQL/deployment/rollback and owner commands](../../docs/DAILY_NUMERIC_PRECISION.md).
This supersedes earlier daily integer-money/float instructions; prior test observations remain historical evidence.


## Stock Daily Data Quality V1 — 3 November 2026

SSI v3 Stock Daily now uses VALID/PARTIAL/REJECTED, field-level NULL quarantine,
immutable RAW and current/history issue evidence. Owner must apply
`20261103_stock_daily_quality_v1.sql` before new writers; historical status stays NULL.
New read-only diagnostic: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Existing `stock-eod`/`stock-eod-backfill` names remain; no automatic backfill/features.
[Policy, deployment, verification SQL and scoped rerun](../../docs/STOCK_DAILY_QUALITY_V1.md).


Provider-independent validation and completeness; never fabricate candles or run features automatically.

Existing feature formulas and historical provenance are unchanged. Stock Daily V1 requires the migration above; any source-data rerun is explicit.

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## SSI v3 Phase 0 diagnostics

`phase0.py` verifies canonical-table catalog metadata and RPC security, then reconciles persisted 1m/1d/15m/60m. 1m requires no feature row. Only ssi_v3 is remapped; legacy/NULL/ambiguous evidence stays UNKNOWN, verified contradictions FAIL. Intraday volume/value use exact integers with no fallback/zero fill. Pure aggregation is reused only with sufficient evidence; no indicators or feature writes. All reads are scoped/bounded, with no migration, data modification or backfill. [Runbook](../../scripts/checks/README.md).
