# src/ingest/workflows

Stock EOD orchestration and workflow date resolution; intraday workflow is explicitly unavailable.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `stock_eod.py`
- `stock_intraday.py`
- `workflow_dates.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
