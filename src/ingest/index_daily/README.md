# src/ingest/index_daily

ACTIVE: index daily ingest/backfill/preview using persisted master scope and v3 adapter.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `index_backfill.py`
- `index_daily.py`
- `index_daily_fetcher.py`
- `index_daily_mapper.py`
- `index_daily_persistence.py`
- `index_daily_preview.py`
- `index_daily_service.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
