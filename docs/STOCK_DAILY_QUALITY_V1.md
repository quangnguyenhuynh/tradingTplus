# Stock Daily Data Quality V1

[Tiếng Việt](STOCK_DAILY_QUALITY_V1.vi.md)

## Investigation and scope

Audited `dev` at `6284b4f4273df7e10c3a10b571ef4bb80a3bfe69` before editing. The mapper discarded the entire candidate on any error, including optional `foreign_remaining_room: BELOW_MINIMUM`. The daily validator only emitted application logs. The stock backfill runner ignored errors returned inside failed ingest summaries, producing FAILED with zero top-level errors. These behaviors prevented safe partial CLEAN writes and durable explanations.

Read-only Supabase catalog inspection confirmed the actual `stock_daily`, `stock_raw_daily` and `stock_data_quality_logs` definitions, CLEAN identity `(symbol,trading_date)`, RAW identity `(symbol,trading_date,source,data_hash)`, existing log unique index `(symbol,trading_date,check_name)`, and service-role table/sequence privileges. No production market rows were read or written. The owner-confirmed TCB failures are 05/03/2026 and 06/03/2026; tests replay the existing realistic v3 fixture shape with illustrative room `-1`, not verbatim TCB responses. SSI credentials were unavailable; no live SSI call was made.

Only SSI v3 Stock Daily changes. Index, intraday, contracts/mappings, feature formulas, existing EOD names and exit policy remain unchanged. The shared mapping result exposes an additive `partial_candidate`; ordinary mapping remains strict. No new dependency or table.

## Policy `stock_daily_validation_v1.0.0`

| Decision | CLEAN | Quality log |
| --- | --- | --- |
| VALID | Persist with `validation_status=VALID` | No new issue row; resolve an existing V1 row |
| PARTIAL | Persist valid fields with `validation_status=PARTIAL`; quarantine affected fields to NULL | ACTIVE issues |
| REJECTED | Never insert/overwrite CLEAN | ACTIVE rejection, RAW retained |
| Historical NULL | Not yet revalidated under V1 | Never inferred to be VALID |

Mandatory symbol/date must match the request. All OHLC prices must be finite, positive, correctly ordered and parseable. Missing, zero or negative OHLC rejects; V1 does not invent a no-trade price. Populated match volume/value must be finite, nonnegative and parseable. Missing `total_match_vol`/`total_match_val` remains NULL with a warning and PARTIAL, consistent with the existing nullable contract. Explicit zero matches with positive valid OHLC can pass; missing matches never imply zero or a confirmed no-trade session. Integer source values are checked exactly, including conflicting aliases and fractions.

The explicit optional allowlist is `price_change`, `per_price_change`, `average_price`, `foreign_remaining_room`, `foreign_total_room`, `foreign_buy_vol_total`, `foreign_sell_vol_total`, `foreign_buy_val_total`, `foreign_sell_val_total`, `total_deal_vol`, `total_deal_val`, `total_buy_trade`, `total_buy_trade_vol`, `total_sell_trade`, `total_sell_trade_vol`.

Only `BELOW_MINIMUM` and unambiguous `TRANSFORM_ERROR` on this list recover by SET_NULL. Missing mapped optional values yield `MISSING_OPTIONAL`/KEEP_NULL warnings. Existing validator codes `DAILY_NON_POSITIVE_PRICE`, `DAILY_PRICE_CHANGE_MISMATCH`, `DAILY_PERCENT_CHANGE_MISMATCH` recover only for allowlisted optional fields. Differing non-null aliases, ambiguous failed aliases, invalid mapping configuration, unknown structural errors, multiple source records and inconsistent identity reject. Unsupported/unmapped fields do not create missing-value warnings. Recovery is versioned here, not a global numeric-contract relaxation.

A negative `remainForeignRoom` keeps its original meaning and RAW value, becomes NULL only in CLEAN, and records original code BELOW_MINIMUM. This quarantine makes no claim about SSI semantics. `total_traded_vol`, `total_traded_value`, `net_foreign_vol`, `net_foreign_val` require both inputs; a missing/quarantined input propagates NULL. No fabricated zero defaults.

## Persistence and provenance

The adapter uses the pure policy; the service persists immutable RAW first, then invokes `persist_stock_daily_validation_v1` once. The RPC atomically locks `(symbol,date)`, merges CLEAN, writes/resolves the existing quality log and verifies both readbacks. It runs SECURITY INVOKER with an empty search path, execute restricted to service_role, with existing table privileges/RLS retained. Invalid acknowledgment, missing migration, log failure or trigger-skipped write fails processing. There is no automatic RPC retry after an ambiguous response. RAW is a separate committed step and can remain without CLEAN; inspect/reconcile explicitly before rerunning. A lost HTTP acknowledgment can mean the transaction committed; the CLI reports failure rather than asserting success.

REJECTED never overwrites CLEAN. Existing VALID plus new PARTIAL becomes REJECTED with `CLEAN_VALID_DOWNGRADE_BLOCKED`, preserving the VALID row. For other accepted writes, a new NULL never erases a known old field. `preserved_fields`, issue action KEEP_EXISTING_FIELD and `previous_clean_raw_hash` explain retained evidence; derived fields are recomputed from the final retained inputs with NULL propagation. A retained value can therefore originate from previous RAW rather than the current payload. The previous hash can be NULL for legacy provenance that cannot be reconstructed. A corrected, issue-free payload promotes PARTIAL to VALID. Original `created_at` remains; application audit time updates `updated_at`.

## Current issues and history

Stable current identity: `(symbol,trading_date,check_name='stock_daily_validation_v1')`; timeframe `1d`. Exactly one current row per identity, not one row per attempt. ACTIVE describes the latest attempt and can coexist with a protected VALID CLEAN row. RESOLVED means the latest accepted revalidation is issue-free. It does not erase historical evidence.

`details` includes dataset/source, raw SHA256 reference, policy/mapping/contract versions, source/final decisions, evaluated time, issues, preserved fields, prior CLEAN RAW hash, clean_persistence_permitted, deterministic fingerprint and history. Each issue has field/code/severity/action/message, for example:

```json
{"field":"foreign_remaining_room","code":"BELOW_MINIMUM","severity":"ERROR","action":"SET_NULL","message":"Value below the allowed minimum"}
```

No entire RAW payload is duplicated in logs. Fingerprints cover RAW hash, policy, final decision, issues and preserved fields. Identical replays update current evidence without appending history; changed prior snapshots append once per fingerprint. Alternating known outcomes do not grow duplicate history indefinitely. New distinct RAW/issues can grow history; review storage operationally. Resolution retains previous issue snapshots in history, sets status RESOLVED/count 0. VALID with no prior issues creates no log.

## Read-only inspection

```bash
python main.py stock-eod-quality --symbols TCB --date 05/03/2026
python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing > tcb-quality.json
```

Reads persisted RAW/CLEAN only; no SSI request or DB/feature/log write. Same policy as ingest. Scope is 1–50 explicit symbols and at most 31 calendar days, bounded 100-row pages and 10,000 rows per table, stable identity/order/count checks. Narrow scope on cap/count errors. Output includes mapping/policy issues, replay decision, CLEAN presence, stored nullable validation_status and field/code counts. Replay is a prediction for one RAW payload, not proof an RPC write would succeed or reproduce historical multi-record/HTTP/DB/log context. Missing CLEAN is marked `UNDETERMINED_RAW_ONLY`; historical persistence failures cannot be reconstructed from RAW alone. Multiple RAW versions are inspected separately. The CLI suppresses DB exception text to avoid exposing configuration.

Read current issues separately, since replay does not replace persisted issue state:

```sql
SELECT symbol,trading_date,status,severity,issue_count,
       details->>'decision' AS decision,details->>'raw_hash' AS raw_hash,
       details->'issues' AS issues,details->'preserved_fields' AS preserved_fields
FROM public.stock_data_quality_logs
WHERE check_name='stock_daily_validation_v1' AND timeframe='1d'
  AND status='ACTIVE' AND symbol='TCB'
  AND trading_date BETWEEN DATE '2026-03-05' AND DATE '2026-03-06';

SELECT symbol,trading_date,status,details->'history' AS history
FROM public.stock_data_quality_logs
WHERE check_name='stock_daily_validation_v1' AND symbol='TCB'
  AND trading_date BETWEEN DATE '2026-03-05' AND DATE '2026-03-06';
```

## Owner deployment and rollback

Migration: [`20261103_stock_daily_quality_v1.sql`](../migrations/20261103_stock_daily_quality_v1.sql). Manually authored using the repository date-prefix convention; Supabase CLI is unavailable in this environment. Owner applies manually, never as an ingest side effect.

1. Pause stock daily scheduled/manual writers and finish in-flight runs. Review/backup schema and scoped data under the owner's normal process.
2. Owner applies migration: one nullable text column with NULL/VALID/PARTIAL check, reuse/ensure existing log unique index, one restricted invoker RPC. No historical status or market value rewrite; no new table. Five-second lock timeout fails instead of waiting indefinitely. Existing duplicate log identities cause explicit failure; no silent deduplication. The unique index can take a table lock if absent.
3. Run read-only catalog verification below and deploy the matching application. Do not mix old writers with V1: old generic upserts do not enforce the new merge/status rules. New app before migration fails and can leave RAW-only evidence. Confirm existing service_role privileges and PostgREST schema-cache visibility before resuming writes.
4. Run the scoped read-only diagnostic and inspect issue state/RAW. The owner may then explicitly run only the backfill below. Check resulting CLEAN statuses, issues and provenance afterward.
5. Resume writers. Features require a separate explicit operator decision after validating inputs. Existing feature code is unchanged and does not automatically filter PARTIAL; downstream users must account for nullable quarantined fields/status.

```sql
SELECT column_name,data_type,is_nullable FROM information_schema.columns
WHERE table_schema='public' AND table_name='stock_daily' AND column_name='validation_status';
SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='public.stock_daily'::regclass AND conname='stock_daily_validation_status_v1_check';
SELECT indexname,indexdef FROM pg_indexes
WHERE schemaname='public' AND tablename IN ('stock_daily','stock_raw_daily','stock_data_quality_logs');
SELECT p.proname,p.prosecdef,p.proconfig,
 has_function_privilege('anon',p.oid,'EXECUTE') AS anon_execute,
 has_function_privilege('authenticated',p.oid,'EXECUTE') AS authenticated_execute,
 has_function_privilege('service_role',p.oid,'EXECUTE') AS service_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname='persist_stock_daily_validation_v1';
SELECT validation_status,count(*) FROM public.stock_daily GROUP BY 1;
SELECT symbol,trading_date,validation_status,foreign_remaining_room,source,updated_at
FROM public.stock_daily WHERE symbol='TCB'
 AND trading_date BETWEEN DATE '2026-03-05' AND DATE '2026-03-06';
```

Expected RPC: invoker (`prosecdef=false`), anon/authenticated false, service_role true. Existing historical statuses remain NULL after migration. Runtime additionally requires schema usage, CLEAN/log SELECT/INSERT/UPDATE, RAW SELECT and log-sequence USAGE (verified in the inspected catalog); do not broaden public grants.

Rollback: pause V1 writers, deploy the prior app deliberately, retain nullable status and quality evidence. Prior application ignores V1 metadata and must not be treated as enforcing V1. Remove the RPC/check/column only in a separately reviewed schema rollback after dependent code is removed; do not delete logs/RAW or rewrite market values. Migration does not restore values from later ingests.

## Explicitly scoped rerun — WRITE, owner only

After migration, matching application and diagnostic review, optional operator action (not executed by this task):

```bash
python main.py stock-eod-backfill --from 05/03/2026 --to 06/03/2026 --symbols TCB --data-source ssi_v3
```

This calls SSI and writes RAW/CLEAN/issues. Existing active-symbol and eligible-date rules apply. Do not widen scope automatically. Previously RAW-only optional failures become eligible if current source core fields pass. Old RAW is not modified. No automatic feature rerun. Existing `stock-eod`/`stock-eod-backfill` names, date aliases and source options remain compatible; no removed aliases return. PARTIAL retains existing exit policy, so inspect JSON status rather than shell exit alone.

Summaries expose `valid_clean_writes`, `partial_clean_writes`, `rejected_records`, `mapping_failures` (records with mapping errors, including recovered ones), `validation_issues` (issue entries), `persistence_failures`. Stock-only backfill now aggregates returned ingest errors and counts, preventing FAILED/zero-error output. Top-level EOD is PARTIAL when daily writes are PARTIAL even if presence checks pass. CLI per-symbol summaries omit full payloads.

## Verification and limitations

Commands run offline (with repository virtualenv activated):

```bash
source .venv/bin/activate
python -m pytest -q tests/validation/test_stock_daily_v1.py tests/validation/test_stock_daily_diagnostic.py tests/validation/test_stock_daily_v1_postgres.py tests/database/test_stock_daily_quality_rpc.py tests/ingest/test_daily_ingest_payload_reuse.py tests/data_sources/test_ssi_v3_stock_daily.py tests/pipeline/test_backfill_pipeline.py tests/pipeline/test_stock_eod_pipeline.py
python -m pytest -q
python -m compileall -q main.py src scripts tests
python main.py --help
python main.py stock-eod-quality --help
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
git diff --check
```

Local baseline after implementation: 69 passed / 8 skipped focused; 1,284 passed / 18 skipped full suite. No relevant failing test. Eight new SQL tests require disposable local `TEST_DATABASE_URL`; no local PostgreSQL/Docker daemon was available. Existing CI supplies PostgreSQL 16 to execute atomicity, migration replay, historical NULL, idempotency/resolution, value preservation, downgrade protection, invoker privileges and trigger-skipped-write tests. Final CI result is recorded in the PR. No live SSI verification or production migration/backfill/write was performed. Catalog-only access does not prove production ingest after deployment; the owner must run the scoped checks above.

## File inventory

### Modified

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_PIPELINE.md`
- `docs/README.md`
- `docs/README.vi.md`
- `docs/STOCK_EOD_PIPELINE.md`
- `docs/STOCK_EOD_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `migrations/README.md`
- `migrations/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/cli/stock.py`
- `src/contracts/engine.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/database/client.py`
- `src/ingest/maintenance/backfill.py`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_daily/daily.py`
- `src/ingest/stock_daily/daily_mapper.py`
- `src/ingest/stock_daily/daily_service.py`
- `src/ingest/workflows/stock_eod.py`
- `src/providers/ssi/adapters/v3.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/validators/README.md`
- `src/quality/validators/README.vi.md`
- `tests/data_sources/test_ssi_v3_stock_daily.py`
- `tests/ingest/test_daily_ingest_payload_reuse.py`
- `tests/pipeline/test_backfill_pipeline.py`

### Created

- `docs/STOCK_DAILY_QUALITY_V1.md`
- `docs/STOCK_DAILY_QUALITY_V1.vi.md`
- `migrations/20261103_stock_daily_quality_v1.sql`
- `src/quality/stock_daily_diagnostics.py`
- `src/quality/validators/stock_daily_v1.py`
- `tests/database/test_stock_daily_quality_rpc.py`
- `tests/validation/test_stock_daily_diagnostic.py`
- `tests/validation/test_stock_daily_v1.py`
- `tests/validation/test_stock_daily_v1_postgres.py`

No files deleted.
