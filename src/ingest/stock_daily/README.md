# src/ingest/stock_daily

ACTIVE: stock daily raw/clean service through the verified v3 adapter.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `daily.py`
- `daily_fetcher.py`
- `daily_mapper.py`
- `daily_persistence.py`
- `daily_service.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
