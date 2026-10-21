# previews — tool runbook

[Tiếng Việt](README.vi.md) · [CLI](../../docs/CLI_USAGE.md)

Run from the root with the Python 3.11 venv and requirements installed. Stock dates accept DD/MM/YYYY or ISO; Phase 0 reconciliation requires ISO. Parser success is separate from data validity; examples were checked offline only. NOT_IMPLEMENTED scripts retain compatibility options but never call SSI/DB, even with --write; help exits 0, operational invocation returns FAILED/NOT_IMPLEMENTED JSON and exit 1.

## `scripts/previews/run_features.py`

Invoke persisted feature engine manually; writes despite previews location.

**WRITE — feature calculation**. Dependency: Supabase only / chỉ Supabase. Output: Feature engine complete: N records; exit 0 after return, exceptions propagate / exception truyền ra.

```bash
python scripts/previews/run_features.py --mode incremental --symbols SSI --timeframes 1d
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--mode` | choices=['full', 'incremental'], default='incremental' |
| `--symbols` | nargs='*', default=None |
| `--timeframes` | nargs='*', default=list(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES) |

## `scripts/previews/eod_dry_run.py`

Former combined EOD diagnostic; disabled on stock_intraday capability.

**NOT_IMPLEMENTED**. Dependency: None / không có. Output: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/previews/eod_dry_run.py --help
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--date` | default=None |
| `--symbols` | nargs='*', default=DEFAULT_SYMBOLS |
| `--timeframes` | nargs='*', default=DEFAULT_TIMEFRAMES |
| `--json` | action='store_true' |

## Write safety

run_features writes `stock_features`, reading `stock_daily` for 1d and clean 1m `stock_intraday` for 15m/60m plus daily context. It never persists 1m/5m features or aggregate source candles. Mode defaults incremental, omitted symbols use engine scope, default timeframes are 15m 60m 1d. There is no --date, --dry-run or --apply; do not run it merely to preview. A record count does not verify completeness. Its previews naming/location is a separate code issue; this documentation task does not change the script.

eod_dry_run retains --date, --symbols (SSI HPG FPT), --timeframes (15m 60m 1d) and --json but does not execute source dry-run or features. Restoring the former pipeline requires a verified v3 intraday adapter.
