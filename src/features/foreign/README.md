# src/features/foreign

ACTIVE: unchanged foreign EOD formulas and existing stock_foreign_features_daily persistence.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `calculator.py`
- `calendar.py`
- `loader.py`
- `persistence.py`
- `service.py`
- `validator.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.

---

# Foreign EOD Feature V2

This independent derived pipeline reads only `stock_daily`. Windows are the last 5/10/20 rows of the same symbol ordered by `trading_date`; no calendar is read or inferred. See [`docs/FOREIGN_EOD_FEATURES.md`](../../docs/FOREIGN_EOD_FEATURES.md) for formulas, quality, CLI, migration, and rollout.
