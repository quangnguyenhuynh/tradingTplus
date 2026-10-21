# src/ingest/master

NOT_IMPLEMENTED: master synchronization. Pure historical models/scope and operator-controlled status contracts remain; no master tables are modified by disabled entrypoints.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `index_master.py`
- `init_symbols.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
