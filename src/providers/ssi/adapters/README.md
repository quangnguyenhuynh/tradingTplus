# src/providers/ssi/adapters

Provider payload mapping to AdapterResult; no ingest/database imports.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `v3.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

## Master registry

`master_contract.py`, `master_registry.py` and `adapters/master_v3.py` isolate master readiness from daily/intraday readiness. SSI v3 master datasets are BLOCKED; no v4/v5 implementation. No master source fields are verified yet. [Contracts, extension steps and evidence audit](../../../ingest/master/README.md).
