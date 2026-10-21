# scripts/checks

Explicit read-only database/schema/completeness checks; combined legacy ingest smoke tool unavailable.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `check_complete_ssi_ingest.py`
- `check_ingest.py`
- `check_ssi_ingest_schema.py`
- `check_supabase.py`
- `phase0_reconcile_sample.py`
- `phase0_validate_schema.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
