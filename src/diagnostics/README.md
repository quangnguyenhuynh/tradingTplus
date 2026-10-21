# src/diagnostics

[Tiếng Việt](README.vi.md)

## Data quality and completeness tools

All active checks below are READ-ONLY — database read. `check_ingest.py` checks persisted stock daily/intraday coverage; it always returns 0 after printing a successful function result, so inspect its JSON completeness status. Intraday missing data is still reportable while ingestion is disabled. `check_supabase.py` has no CLI arguments or help parser: it performs core-table connectivity checks, not comprehensive schema certification. `check_ssi_ingest_schema.py` selects listed columns and prints index verification SQL; its legacy column expectations may be stale against contract 2.0 and need a separate code fix, not schema changes to satisfy the diagnostic.

`phase0_validate_schema.py` uses read-only PostgreSQL catalog queries; prefer the environment variable over putting a database URL in shell history. `phase0_reconcile_sample.py` checks one symbol/date/timeframe, optional exact timestamp and tolerance 1e-6. PASS/FAIL/UNKNOWN matter independently of process execution. See [checks](../../scripts/checks/README.md).

```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
python scripts/checks/check_supabase.py
python scripts/checks/check_ssi_ingest_schema.py
python scripts/checks/phase0_validate_schema.py
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
```
## Diagnostic, maintenance and debug scripts

The [script inventory](../../scripts/README.md) covers every executable tool at its current location. **`scripts/previews/run_features.py` is WRITE — feature calculation**, despite its directory name. It invokes the engine, has no dry-run or date flag, and may process all selected history according to mode/watermarks. Prefer explicit main.py feature routes for a target date. Its naming/location is a separate code issue; it was not moved here.

`eod_dry_run.py`, `fetch_one_day.py`, capture scripts, streaming inspector and complete SSI smoke check are disabled stubs, not working debug pipelines. The legacy intraday-value SQL is a broad WRITE artifact without symbol/date scoping; it is not a routine operational CLI and must not be pasted into production. A separately reviewed scoped repair is required.

```bash
python scripts/previews/run_features.py --mode incremental --symbols SSI --timeframes 1d
```

[CLI](../../docs/CLI_USAGE.md)
