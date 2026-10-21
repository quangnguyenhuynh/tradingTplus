# maintenance — tool runbook

[Tiếng Việt](README.vi.md) · [CLI](../../docs/CLI_USAGE.md)

Run from the root with the Python 3.11 venv and requirements installed. Stock dates accept DD/MM/YYYY or ISO; Phase 0 reconciliation requires ISO. Parser success is separate from data validity; examples were checked offline only. NOT_IMPLEMENTED scripts retain compatibility options but never call SSI/DB, even with --write; help exits 0, operational invocation returns FAILED/NOT_IMPLEMENTED JSON and exit 1.

## `scripts/maintenance/fetch_one_day.py`

Former one-symbol/day source diagnostic; disabled on stock_intraday.

**NOT_IMPLEMENTED**. Dependency: None / không có. Output: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/maintenance/fetch_one_day.py --help
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | required=True |
| `--date` | required=True |
| `--dry-run` | action='store_true', default=True |
| `--write` | action='store_true' |

## `scripts/maintenance/backfill_stock_intraday_value.sql`

**WRITE — broad unscoped maintenance artifact, not a safe production CLI.** The current SQL updates all stock_intraday rows with null value and non-null close/volume using close * volume. It has no flags, scope or confirmation. This is estimated value, not exchange turnover; invalid inputs must remain null and current rounding semantics need review. Do not execute the file wholesale. A separately reviewed repair needs exact scope, before/after counts, backup/rollback and appropriate PostgreSQL rights. This documentation task does not execute SQL or require backfill.

fetch_one_day retains required --symbol/--date and mutually exclusive --dry-run/--write; it still returns NOT_IMPLEMENTED before any service access. --write cannot enable intraday ingestion. Historical clean data remains usable for features.
