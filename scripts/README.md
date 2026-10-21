# Operational script inventory

[Tiếng Việt](README.vi.md) · [CLI](../docs/CLI_USAGE.md)

Run from the root after installing requirements in a venv. Classification follows executable behavior, not directory names. Do not execute WRITE examples to validate documentation. Linked directory guides provide examples, arguments, dependencies, output, exit behavior and safety limits.

| Tool | Purpose | Classification | Dependencies |
| --- | --- | --- | --- |
| [checks/check_ingest.py](checks/README.md) | Check persisted daily/intraday completeness | READ-ONLY — database read | Supabase |
| [checks/check_supabase.py](checks/README.md) | Check connectivity to core tables | READ-ONLY — database read | SUPABASE_URL + SUPABASE_SERVICE_KEY |
| [checks/check_ssi_ingest_schema.py](checks/README.md) | Select required columns and print constraint-check SQL | READ-ONLY — database read | Supabase |
| [checks/phase0_validate_schema.py](checks/README.md) | Verify PostgreSQL catalog with a read-only transaction | READ-ONLY — database read | PHASE0_DATABASE_URL or --database-url |
| [checks/phase0_reconcile_sample.py](checks/README.md) | Reconcile one bounded raw/clean/feature sample | READ-ONLY — database read | Supabase |
| [checks/check_complete_ssi_ingest.py](checks/README.md) | Former multi-dataset SSI smoke test; disabled on master capability | NOT_IMPLEMENTED | None / không có |
| [previews/run_features.py](previews/README.md) | Invoke persisted feature engine manually; writes despite previews location | WRITE — feature calculation | Supabase only / chỉ Supabase |
| [previews/eod_dry_run.py](previews/README.md) | Former combined EOD diagnostic; disabled on stock_intraday capability | NOT_IMPLEMENTED | None / không có |
| [maintenance/fetch_one_day.py](maintenance/README.md) | Former one-symbol/day source diagnostic; disabled on stock_intraday | NOT_IMPLEMENTED | None / không có |
| [capture/snapshot_stream.py](capture/README.md) | Former bounded stream capture; disabled pending verified v3 protocol | NOT_IMPLEMENTED | None / không có |
| [capture/snapshot_orderbook.py](capture/README.md) | Former depth snapshot capture; disabled pending verified v3 streaming | NOT_IMPLEMENTED | None / không có |
| [inspectors/ssi_streaming/inspect.py](inspectors/ssi_streaming/README.md) | Former negotiate/run inspector; every subcommand including list is disabled | NOT_IMPLEMENTED | None / không có |
| [inspectors/ssi_rest/inspect.py](inspectors/ssi_rest/README.md) | Inspect SSI v3 raw/clean | READ-ONLY — SSI API request | SSI v3 (run) |
| [maintenance/backfill_stock_intraday_value.sql](maintenance/README.md) | Unscoped value repair SQL | WRITE — do not execute wholesale | PostgreSQL |

`__init__`, client, registry, datasets, endpoints, mapping and output modules are support libraries, not independent operational CLIs. run_features under previews writes stock_features with no dry-run: its naming/location needs a separate code task. This documentation task has no DB/migration/backfill impact.
