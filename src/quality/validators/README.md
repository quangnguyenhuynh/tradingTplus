# src/quality/validators

Canonical typed-row validation, logging and bounded read-only Phase 0 diagnostics.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `daily_validator.py`
- `index_daily_validator.py`
- `intraday_validator.py`
- `logging_utils.py`
- `models.py`
- `phase0.py`
- `streaming_validator.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
