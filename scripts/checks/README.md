# checks — tool runbook

[Tiếng Việt](README.vi.md) · [CLI](../../docs/CLI_USAGE.md)

Run from the root with the Python 3.11 venv and requirements installed. Stock dates accept DD/MM/YYYY or ISO; Phase 0 reconciliation requires ISO. Parser success is separate from data validity; examples were checked offline only. NOT_IMPLEMENTED scripts retain compatibility options but never call SSI/DB, even with --write; help exits 0, operational invocation returns FAILED/NOT_IMPLEMENTED JSON and exit 1.

## `scripts/checks/check_ingest.py`

Check persisted daily/intraday completeness.

**READ-ONLY — database read**. Dependency: Supabase. Output: JSON; exit 0 after return; inspect JSON status / đọc trạng thái JSON.

```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--date` | required=True |
| `--symbols` | nargs='+', default=None |

## `scripts/checks/check_supabase.py`

Check connectivity to core tables.

**READ-ONLY — database read**. Dependency: SUPABASE_URL + SUPABASE_SERVICE_KEY. Output: Per-table PASS/FAIL; exit 0 pass, 1 failures, 2 missing config / thiếu cấu hình.

```bash
python scripts/checks/check_supabase.py
```

No CLI arguments; check_supabase has no help parser.

## `scripts/checks/check_ssi_ingest_schema.py`

Select required columns and print constraint-check SQL.

**READ-ONLY — database read**. Dependency: Supabase. Output: Table/column PASS/FAIL; exit 1 failures, 0 otherwise / khi không lỗi.

```bash
python scripts/checks/check_ssi_ingest_schema.py
```

No CLI arguments; check_supabase has no help parser.

## `scripts/checks/phase0_validate_schema.py`

Verify PostgreSQL catalog with a read-only transaction.

**READ-ONLY — database read**. Dependency: PHASE0_DATABASE_URL or --database-url. Output: JSON PASS/FAIL/UNKNOWN; exit 0/1/2.

```bash
python scripts/checks/phase0_validate_schema.py
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--database-url` | default=os.getenv('PHASE0_DATABASE_URL') |

## `scripts/checks/phase0_reconcile_sample.py`

Reconcile one bounded raw/clean/feature sample.

**READ-ONLY — database read**. Dependency: Supabase. Output: Payload + reconciliation JSON; exit 1 FAIL, 2 UNKNOWN, 0 otherwise.

```bash
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 15m --tolerance 0.000001
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | required=True |
| `--date` | required=True |
| `--timeframe` | required=True, choices=('1d', '15m', '60m') |
| `--timestamp` |  |
| `--tolerance` | type=float, default=1e-06 |

## `scripts/checks/check_complete_ssi_ingest.py`

Former multi-dataset SSI smoke test; disabled on master capability.

**NOT_IMPLEMENTED**. Dependency: None / không có. Output: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/checks/check_complete_ssi_ingest.py --help
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | default='SSI' |
| `--date` | default=None |
| `--index-code` | default='VNINDEX' |
| `--write` | action='store_true' |
| `--write-intraday` | action='store_true' |
| `--force` | action='store_true' |

## Interpretation and limitations

check_ingest never repairs data; a universal candle count cannot certify a session. check_supabase selects one row per table and does not verify unique indexes. check_ssi_ingest_schema still expects some pre-contract-2.0 index/foreign columns; FAIL may reflect a stale diagnostic rather than invalid current schema. Do not recreate old columns to make it pass; fix the diagnostic in a separate code task. Phase 0 can return UNKNOWN when source/schema evidence is absent; do not promote it to PASS. Optional --timestamp targets an exact intraday feature row; tolerance defaults to 1e-6. --database-url defaults to PHASE0_DATABASE_URL; keep actual URLs out of logs and shell history.

check_complete_ssi_ingest retains --symbol (SSI), --date, --index-code (VNINDEX), --write, --write-intraday and --force but all operations are disabled; it cannot prove v3 ingestion works. The stub needs no credentials.
