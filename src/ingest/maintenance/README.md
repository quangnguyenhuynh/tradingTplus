# src/ingest/maintenance

Daily-only backfill is active; combined/intraday backfill and refill are unavailable before any stage.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `backfill.py`
- `refill.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
