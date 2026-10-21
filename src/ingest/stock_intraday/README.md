# src/ingest/stock_intraday

NOT_IMPLEMENTED: new 1m ingestion. Pure timestamp/dedup helpers, canonical validators and persistence boundaries remain reusable; existing clean data remains usable.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `intraday_fetcher.py`
- `intraday_ingest.py`
- `intraday_mapper.py`
- `intraday_persistence.py`
- `intraday_service.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
