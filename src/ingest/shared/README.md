# src/ingest/shared

## EOD backfill ownership — 5 November 2026

| Responsibility | Canonical module |
| --- | --- |
| Stock runner + `_run_ingest_backfill` | `src/ingest/stock_daily/backfill.py` |
| Index runner | `src/ingest/index_daily/index_backfill.py` |
| Five shared range/report helpers | `src/ingest/shared/backfill_range.py` |
| Guarded Intraday and legacy compatibility | `src/ingest/maintenance/backfill.py` |

Stock/Index consume shared helpers directly. Maintenance re-exports the Stock
runner and old helper names without copying logic. Public `src.ingest` import
names remain; the Stock lazy export now points to its domain. CLI handlers keep
using the same public exports. No CLI/options/JSON flow, algorithm, policy,
persistence or guard change. This refactor needs no migration or data backfill.

[Move, compatibility and verification report](../../../docs/backfill/README.md).


Date parsing, active symbol/index scopes and pipeline status helpers shared without provider calls.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `backfill_range.py`
- `date_utils.py`
- `index_scope.py`
- `pipeline_status.py`
- `symbol_scope.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
