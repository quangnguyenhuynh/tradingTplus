# src/providers/ssi/adapters

Provider payload mapping to AdapterResult; no ingest/database imports.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `v3.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## Verified security master

`master_v3.py` implements shared strict `securitiesByBoard` fetch/mapping for HOSE/HNX/UPCOM. Symbols/securities are guarded READY; both index capabilities remain unchanged BLOCKED. No authoritative provider total: market completeness UNVERIFIED. All instrument types retained; no automatic eligibility. [Mapping, anomaly guards, evidence and owner recovery](../../../ingest/master/README.md).

## Unified master cutover — 27 October 2026

This supersedes earlier independent symbols/securities procedures: symbols is the sole physical write target; securities is a deprecated CLI alias with an explicit warning. all syncs symbols once. Apply Stage A expansion/merge BEFORE application deployment; Stage B retirement is separately owner-approved and aborts by default. Never apply production migrations through the agent. VN50 GROWTH exact index exclusion is counted; HNX-request DERIVATIVES/Future retains its actual domain and inactive defaults. Index capabilities remain BLOCKED. No price backfill. [Runbook](../../../ingest/master/README.md).
