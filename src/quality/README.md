# src/quality

Provider-independent validation and completeness; never fabricate candles or run features automatically.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## SSI v3 Phase 0 diagnostics

`phase0.py` verifies canonical-table catalog metadata and RPC security, then reconciles persisted 1m/1d/15m/60m. 1m requires no feature row. Only ssi_v3 is remapped; legacy/NULL/ambiguous evidence stays UNKNOWN, verified contradictions FAIL. Intraday volume/value use exact integers with no fallback/zero fill. Pure aggregation is reused only with sufficient evidence; no indicators or feature writes. All reads are scoped/bounded, with no migration, data modification or backfill. [Runbook](../../scripts/checks/README.md).
