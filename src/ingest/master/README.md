# Unified symbols security master

[Tiếng Việt](README.vi.md)

**Deployment PARTIAL: owner must apply Stage A and verify live before cutover.**
`public.symbols` is the sole authoritative application master write target. Its
original table identity, symbol PK, statuses, created_at and dependent FKs are retained.
Physical securities remains a read-only legacy backup through Stage A; Stage B is optional.

## Schema and migration rules

Retain symbol, market, name, created_at, status, intraday_status. Add nullable
stock_en_name, sec_type, exchange, issuer, lot_size, listed_share, issue_date,
first_trading_date, last_trading_date, maturity_date, tick_price1..4,
tick_increment1..4, raw JSONB, updated_at. Numeric stays numeric, dates stay date.
Legacy stock_name maps to name, market maps to existing market. No duplicate stock_name.
Issuer/issue_date/tick fields have no verified current SSI mapping, but are retained
for lossless legacy migration; sync never fabricates them. Existing non-null fields
are not overwritten by missing source values. Raw conflicts abort, not silently merge.

Stage A migration: migrations/20261027_expand_symbols_master.sql. Pause all master
writers and back up both tables, grants, dependency definitions. The transactional
migration locks both tables; adds columns; aborts on ANY conflicting non-null
source-owned field (including name/market/raw); fills only target NULLs. Existing
status/intraday_status/created_at win exactly. Securities-only rows insert inactive/
inactive; created_at stays NULL because legacy creation time is unknown. Existing
updated_at wins, otherwise legacy audit timestamp. No price/feature rows touched.
Rerun is idempotent unless a later conflicting legacy value exists, then explicit abort.
No table recreation, FK/PK replacement, deletion or destructive overwrite.

Preflight: inspect overlap using the following and review every descriptive field
listed in the migration mapping. Resolve conflicts separately with backup/evidence;
the migration never picks a non-null winner silently.

```sql
select count(*) from public.symbols;
select count(*) from public.securities;
select t.symbol,t.name,s.stock_name,t.market,s.market
from public.symbols t join public.securities s using(symbol)
where (t.name is not null and s.stock_name is not null and t.name is distinct from s.stock_name)
or (t.market is not null and s.market is not null and t.market is distinct from s.market);
-- After A: zero missing identities; verify each copied field and operator controls
select s.symbol from public.securities s left join public.symbols t using(symbol) where t.symbol is null;
select status,intraday_status,count(*) from public.symbols group by 1,2;
```

## Application cutover and CLI

Apply A manually BEFORE deploying this application. A missing expanded schema fails
with SYMBOLS_SCHEMA_REQUIRED_APPLY_STAGE_A_OR_CHECK_DB_ACCESS; there is no old-schema
fallback or partial write. Explicit select includes all expanded fields, with numeric
casts to text to avoid SDK float rounding. DB access failures also stop safely.

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --dry-run
# Owner only after inspecting complete preflight:
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --write
python main.py init --dataset symbols --data-source ssi_v3 --dry-run
```

--dataset securities is a DEPRECATED alias, reported as requested_dataset=securities,
canonical_dataset=symbols and warning; same one physical sync with explicit write
required. all previews symbols once plus the two BLOCKED index datasets. No write-all.
Public map_security_record now returns unified name instead of stock_name.
upsert_securities raises an actionable retirement error instead of silently rerouting
or retaining a second unsafe writer. Generic upsert_symbols defaults stay compatible;
guarded sync explicitly inserts inactive/inactive. Existing active ingest selectors
are unchanged: master sync cannot activate stocks, futures, bonds or ETFs. Operator
flags remain operator decisions, never strategy/type inference. No downstream calls.

## Source mapping and verified scope exceptions

SSI v3 securitiesByBoard requests HOSE, HNX, UPCOM; shared existing client/auth and
bounded retries. Every accepted row carries all supported metadata in the symbols
DTO, including sanitized raw. symbolNameVi→name, symbolNameEn→stock_en_name,
board→market/exchange, stockType→sec_type; lotSize/listedShare and three listing/date
fields keep exact conversions. No index-domain merging, no future SSI version guessed.

Owner evidence 27 October: received HOSE795/HNX414/UPCOM852 (2061), not fixed totals.
Only exact HOSE / symbol `VN50 GROWTH` / board HOSE / stockType NULL is excluded as
owner-confirmed indexList identity outside security-master scope. It is NEVER rewritten
VN50GROWTH. Exclusion identity/reason/requested board/count are reported; received =
accepted + explicitly excluded when valid. Any other unexplained spaced identity blocks.
Only HNX-request / actual DERIVATIVES / stockType Future is the verified board exception.
Preserve market DERIVATIVES/sec_type Future/raw and actual-market counts beside request
provenance. Other board mismatches block. New derivatives stay inactive/inactive.

All three responses must succeed. Diagnostics separate received/accepted/excluded/
invalid/duplicate. HTTP body reception is not authoritative market completeness:
UNVERIFIED remains explicit. Historical counts are anomaly references, not permanent
requirements. Existing count-drop, duplicate, malformed, NULL, decimal/date, compare-
and-set, readback and ambiguous-write guards remain. Source cardinality accounts for
exclusions explicitly. Transactions remain per row/request, not multi-table atomic.

## Stage B and rollback

After deployment, owner must verify counts/fields/flags/FKs, run dry-run/write/readback,
rerun idempotency, check every view/matview/RPC/trigger/FK/job/client and take verified
restorable backups. Only then separately approve
migrations/20261027_retire_securities_optional.sql. This file aborts by default;
owner explicitly adds SET LOCAL app.approve_retire_securities =
'owner-reviewed-and-backed-up' after its BEGIN, in the reviewed manual transaction.
DROP uses RESTRICT, never CASCADE. Identity coverage and stored-function references
are checked; catalog checks cannot prove absence of dynamic SQL/external jobs.
Never run B automatically with A. No production migration was executed here.

Rollback A application first; leave expansion columns and new identities intact to
preserve dependent rows. Restore specific descriptions only from backup after review,
never bulk delete/reload. Stage B rollback requires restoring the archived securities
table/data/grants/indexes and compatible application, without deleting symbols.

Audit dev 5e22c5c94053fd446d826fd4f87af9412cd7642e (PR187). Live read-only catalog
confirmed FKs from stock_intraday/partitions, stock_features, stock_foreign_trading,
analog_snapshots, stock_screener_results; no securities FK, views, matviews or triggers;
foreign RPCs use symbols, no stored function references securities, cron.job absent.
Application repository searches found no Flutter client/physical securities consumer
outside master helpers and schema diagnostics (now updated). Owner must repeat audit
at execution time. Observed counts supplied by owner are not migration assumptions.

No migration/production write/live SSI request by agent. No price backfill, feature,
signal, strategy, index capability or schedule change. Local migration execution is
NOT_RUN: Docker socket unavailable and package runtime download blocked. Structural
SQL tests pass; real PostgreSQL migration tests are supplied for disposable CI only.
Production deployment remains PARTIAL until owner executes A and live verification.

## Results and file inventory

158 passed, 3 skipped (focused); 1203 passed, 10 skipped (full suite). Compile/help/diff check PASS. PostgreSQL migration execution NOT_RUN locally; 3 disposable migration tests + 7 existing integration tests require TEST_DATABASE_URL. SQL structural checks passed. No production migration/write or live SSI call.

```bash
.venv/bin/python -m pytest -q tests/ingest/test_unified_master.py tests/ingest/test_unified_master_postgres.py tests/ingest/test_versioned_master_sync.py tests/ingest/test_ssi_v3_master_adapter.py tests/ingest/test_master_data_pipeline.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py sync-master-data --help
.venv/bin/python main.py init --help
git diff --check
```

Modified:

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/SSI_V3_MASTER_EVIDENCE.md`
- `docs/SSI_V3_MASTER_EVIDENCE.vi.md`
- `migrations/README.md`
- `migrations/README.vi.md`
- `schema.sql`
- `scripts/checks/check_ssi_ingest_schema.py`
- `scripts/checks/check_supabase.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/database/client.py`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/master/contracts.py`
- `src/ingest/master/store.py`
- `src/ingest/master/sync.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/README.md`
- `src/providers/ssi/adapters/README.vi.md`
- `src/providers/ssi/adapters/master_v3.py`
- `src/providers/ssi/master_contract.py`
- `tests/ingest/test_ssi_v3_master_adapter.py`
- `tests/ingest/test_versioned_master_sync.py`

Created:

- `migrations/20261027_expand_symbols_master.sql`
- `migrations/20261027_retire_securities_optional.sql`
- `tests/ingest/test_unified_master.py`
- `tests/ingest/test_unified_master_postgres.py`

Deleted: NONE. Migration order: A → deploy → owner verification/backups/approval → optional B. Deployment PARTIAL, not applied.

## CI PostgreSQL verification — 27 October 2026

[Unit Tests run 40465219387](https://github.com/quangnguyenhuynh/tradingTplus/actions/runs/40465219387) on commit `1b9b56d0cf704ffce7dc6eef80ca3e92e5e9629e`: **1213 passed, zero skipped**, PostgreSQL 16 (17.94s). This includes the three migration execution tests (precision/JSONB/status/FK preservation, rerun, conflict rollback and Stage B approval refusal). Earlier NOT_RUN/skip statements above describe local execution only. CI tested disposable data; production migration/deployment remains owner-only and NOT_RUN.
