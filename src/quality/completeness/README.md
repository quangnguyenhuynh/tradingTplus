# src/quality/completeness

Daily/intraday/index persisted-data completeness checks; no universal fixed candle count.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `index_completeness.py`
- `ingest_check.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
