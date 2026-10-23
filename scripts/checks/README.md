# checks — tool runbook

[Tiếng Việt](README.vi.md) · [CLI](../../docs/CLI_USAGE.md)

Run from the root with the Python 3.11 venv and requirements installed. Stock dates accept DD/MM/YYYY or ISO; Phase 0 reconciliation requires ISO. Parser success is separate from data validity; examples were checked offline only. NOT_IMPLEMENTED scripts retain compatibility options but never call SSI/DB, even with --write; help exits 0, operational invocation returns FAILED/NOT_IMPLEMENTED JSON and exit 1.

## `scripts/checks/check_ingest.py`

Check persisted daily/intraday completeness.

**READ-ONLY — database read**. Dependency: Supabase. Output: JSON-only stdout; exit 0 OK, 1 PARTIAL/FAILED or query error, 2 invalid input/indeterminate result. Progress goes to stderr.

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
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m --timestamp 2026-10-21T02:15:00Z
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 15m --tolerance 0.000001
```

| Argument / alias | Parser rules (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | required=True |
| `--date` | required=True |
| `--timeframe` | required=True, choices=('1m', '1d', '15m', '60m') |
| `--timestamp` | Exact timezone-aware instant within requested VN date; 1m candle or 15m/60m feature bucket |
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

## SSI v3 Phase 0 diagnostic contract (2026-10-23)

Schema verification reads catalog metadata for `public.stock_raw_intraday.payload` (JSONB, nullable, no default), `public.stock_features` canonical unique identity `(symbol,timeframe,time)`, and the expected `replace_features_atomic(text,text,timestamptz,timestamptz,jsonb)` signature. A valid/ready full unique primary-key or constraint-backed index qualifies regardless of name/key order; partial, expression, nonunique or invalid indexes do not. RPC checks retain SECURITY DEFINER, empty search_path, service_role EXECUTE and no anon/authenticated/PUBLIC EXECUTE. PUBLIC is checked via ACL grantee 0, not as a named role. No RPC invocation, DDL or repair occurs.

Reconciliation uses persisted data only, never SSI requests or the manual ingest entrypoint. `1m` checks raw → canonical clean and does **not** query or require stock_features. `1d` stays stock_raw_daily → stock_daily → stock_features(1d). `15m/60m` checks raw 1m → clean 1m in the selected bucket, then observed clean → persisted feature OHLCV/value using the existing pure aggregation/closed-bucket helpers. It does not compute indicators or persist features. Other feature columns are outside this diagnostic.

Only raw source `ssi_v3` is mapped with the verified source contract. Legacy `SSI`, unknown sources, missing payloads and incompatible formats report UNKNOWN instead of being reinterpreted or falsely passed. `ohlc.tradingDate` uses the documented Vietnam-local source rule; equivalent UTC offsets compare as the same instant, with seconds preserved. No minute rounding/shifting, source-value estimate or NULL-to-zero substitution. Volume/value compare as exact integers without float conversion/tolerance; OHLC uses the explicit absolute/relative tolerance (default 1e-6).

All reconciliation reads require one explicit symbol and Vietnam date, using half-open UTC bounds. With --timestamp, use the exact aware instant, never a nearby row. Without it, 1m selects the earliest SSI v3 raw instant (or earliest raw of any source if no v3); all raw versions/sources at that instant are considered and multiple candidates return UNKNOWN. Missing raw falls back only to the earliest clean instant to report missing lineage. Higher timeframes select the latest persisted bucket and inspect its observed raw/clean constituents; duplicates fail, source collisions are UNKNOWN. No universal 60-emitted-candle rule: aggregation follows VN date/session grouping, left-labeled buckets, and configured session closure. Open/partial buckets, NULL aggregate inputs or absent evidence are UNKNOWN; no legacy value-fill helper is reached. Closed observed-bucket equality is not proof of full source coverage.

Reads page in 100-row batches with exact-count checks: bounded at 3,000 raw/2,000 clean intraday rows and 200 features per selected day; daily raw/clean/features bounds are 1,000/100/100. Cap/truncation/changing evidence returns UNKNOWN. Retain per-layer results and comparisons. PASS means a verified comparison matched; FAIL means a verified contradiction (and outranks UNKNOWN elsewhere); UNKNOWN means missing/ambiguous/unsupported evidence. WARNING remains available. Reconciliation exit 0 PASS/WARNING, 1 FAIL, 2 UNKNOWN. Payload-presence summary is informational and cannot override the selected lineage result, especially for 1m/daily.

Completeness continues to call the existing check_ingest algorithm unchanged. OK certifies only its structural checks, not full SSI minute coverage; gaps can be no-trade observations and 226 is never an expected universal count. Exceptions are sanitized and nonzero; original returned JSON/status is preserved. All tools remain read-only, without migration, data repair/backfill, ingest, feature calculation, signals or backtests. Manual pilot safety and disabled commands are unchanged.

Owner read-only examples (configure local DB credentials without printing secrets):

```bash
python scripts/checks/phase0_validate_schema.py
python scripts/checks/check_ingest.py --date 21/10/2026 --symbols SSI
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 15m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 60m
```

Retain JSON and exact scope. If that persisted scope has no data, UNKNOWN is expected; do not ingest or repair data merely to turn a diagnostic green. See the [dated verification report](../../docs/phase0/PHASE0_VALIDATION_REPORT.md).
