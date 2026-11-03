# src/quality/validators

## Stock Daily Data Quality V1 — 3 November 2026

SSI v3 Stock Daily now uses VALID/PARTIAL/REJECTED, field-level NULL quarantine,
immutable RAW and current/history issue evidence. Owner must apply
`20261103_stock_daily_quality_v1.sql` before new writers; historical status stays NULL.
New read-only diagnostic: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Existing `stock-eod`/`stock-eod-backfill` names remain; no automatic backfill/features.
[Policy, deployment, verification SQL and scoped rerun](../../../docs/STOCK_DAILY_QUALITY_V1.md).


Canonical typed-row validation, logging and bounded read-only Phase 0 diagnostics.

Existing feature formulas and historical provenance are unchanged. Stock Daily V1 requires the migration above; any source-data rerun is explicit.

Modules:

- `daily_validator.py`
- `index_daily_validator.py`
- `intraday_validator.py`
- `logging_utils.py`
- `models.py`
- `phase0.py`
- `streaming_validator.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## SSI v3 Phase 0 diagnostics

`phase0.py` verifies canonical-table catalog metadata and RPC security, then reconciles persisted 1m/1d/15m/60m. 1m requires no feature row. Only ssi_v3 is remapped; legacy/NULL/ambiguous evidence stays UNKNOWN, verified contradictions FAIL. Intraday volume/value use exact integers with no fallback/zero fill. Pure aggregation is reused only with sufficient evidence; no indicators or feature writes. All reads are scoped/bounded, with no migration, data modification or backfill. [Runbook](../../../scripts/checks/README.md).
