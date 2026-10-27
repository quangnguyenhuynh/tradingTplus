# src/providers/ssi/adapters

Provider payload mapping to AdapterResult; no ingest/database imports.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `v3.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## Verified security master

`master_v3.py` implements shared strict `securitiesByBoard` fetch/mapping for HOSE/HNX/UPCOM. Symbols/securities are guarded READY; both index capabilities remain unchanged BLOCKED. No authoritative provider total: market completeness UNVERIFIED. All instrument types retained; no automatic eligibility. [Mapping, anomaly guards, evidence and owner recovery](../../../ingest/master/README.md).
