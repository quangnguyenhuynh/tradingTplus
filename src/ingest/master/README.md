# Guarded versioned master synchronization

[Tiếng Việt](README.vi.md)

**Implementation status: PARTIAL. Production source validation: BLOCKED.**
`sync-master-data` and compatible alias `init` now execute the new orchestrator.
All four SSI v3 master capabilities are explicitly BLOCKED; this release cannot
bootstrap production master data. No verified master response fixtures or SSI
credentials were available. Nothing is silently promoted to READY.

## Evidence and source boundaries

Audited latest `dev`: `32f03abab80648f15afa80cfeb31ea15027bd44d` (26 October 2026).
The inspector defines candidate requests, not proven response/mapping contracts:

| Dataset | Candidate endpoint | Known request definition | Unresolved evidence |
| --- | --- | --- | --- |
| symbols | `/api/v3/data/securitiesByBoard`, `/api/v3/data/masterdata` | exactly one symbol/board/index selector for securitiesByBoard; masterdata from/to dates plus pageIndex/pageSize | Actual identity/name/board/security-type fields; universe completeness; HOSE/HNX/UPCoM representation |
| securities | same candidates | same definitions | Every detailed field, type and missing-field meaning |
| index_master | `/api/v3/data/indexList` | optional board; inspector single-page | Index identity/name/exchange fields and authoritative complete listing |
| index_components | `/api/v3/data/securitiesByBoard` | candidate index selector | Actual constituent relationship and authoritative complete membership |

There are **zero verified v3 master response fields/mappings** in this release.
The inspector aliases do not establish endpoint equivalence or membership.
Daily securitiesSummary fixtures and OHLC fixtures prove only their own price
contracts. They are not master fixtures. No successful SSI master fixture was
invented. No live SSI request or Supabase write occurred during development.
The v3 adapter raises safe explicit errors if fetched/mapped directly and does
not construct a client. Generic permissive `SSIV3Client.paged()` is not used to
claim complete master pagination. Authentication/retry utilities remain shared
and unchanged; production master fetch/paging implementation awaits evidence.

## CLI and current outcomes

```bash
python main.py sync-master-data
python main.py init --dataset symbols --data-source ssi_v3 --dry-run
python main.py sync-master-data --dataset index_master --data-source ssi_v3 --dry-run
python main.py sync-master-data --help
python main.py init --help
```

Current previews exit **1/BLOCKED**, zero API/DB access. Omitted dataset previews
all four independent datasets. Omitted source selects the newest explicitly
registered verified READY provider per dataset; currently none exists, so each
report says NO_READY_MASTER_PROVIDER and lists the available blocked capability.
An explicit ssi_v3 source reports MASTER_CAPABILITY_NOT_READY. Unknown ssi_v2,
ssi_v4, ssi_v5 or auto sources exit 2; no fallback. Dry-run/write are mutually
exclusive. There are no unverified boards/symbols/index selectors in this CLI.

The future owner write syntax is below, **not a working production example**:

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --write
```

This still exits BLOCKED today. `--write` requires exactly one explicit dataset;
command-only write and `--dataset all --write` exit 2. All is preview-only.
Dataset names: symbols, securities, index_master, index_components. Only status
OK exits 0; PARTIAL, FAILED, BLOCKED and UNSUPPORTED exit 1.

## Architecture and canonical schema

`CLI → run_master_sync → MasterRegistry → version adapter → MasterSnapshot →
canonical validation → compare → MasterStore → JSON`.
Price registry/readiness, clients, Daily/Intraday pipelines and generic DB upsert
defaults are unchanged. The orchestrator contains no SSI endpoint/response names.
The old v2 mapper logic was removed. Public Python sync/map names remain thin
wrappers; map wrappers reject unverified mapping. Legacy injected SSI/DB objects
and index scopes are explicitly rejected instead of starting retired logic.

| Table / unique key | Allowed canonical source-owned fields |
| --- | --- |
| symbols / symbol | market, name |
| securities / symbol | market, stock_name, stock_en_name, sec_type, exchange, issuer, lot_size, listed_share, issue_date, maturity_date, first_trading_date, last_trading_date, tick_price1..4, tick_increment1..4, raw |
| index_master / index_code | index_name, exchange, raw |
| index_components / index_code,symbol | exchange, raw |

These are DB contracts, **not claimed SSI mappings**. Identifier normalization:
trim/uppercase; restricted nonblank identifier; duplicates including normalized
collisions block the whole dataset. Unknown columns and local operator controls
in adapter records are rejected. Decimal fields preserve precision without float;
non-finite, negative and float inputs reject. Dates require canonical ISO dates.
Missing optional values remain NULL/omitted; existing non-null fields are never
overwritten with NULL. No fallback names, inferred boards/types, inactivity,
delisting or membership. Meaningful source distinctions must be verified and
mapped by each future adapter, never discarded by orchestration.

## Guards, comparison and transactions

A usable adapter must supply canonical records, source count, mapping version,
exact resolved scope and complete pagination evidence in MasterSnapshot. Current
CLI contract is full dataset scope only (`{"kind":"ALL"}`). Any source error,
incomplete response, unknown scope, mapping/count mismatch, invalid/duplicate
identity or empty source blocks before DB writes. One source record must account
for each canonical row in this initial contract. No partial subset is written.
An unverified or PREVIEW capability cannot write; default selection excludes it.
A later independent dataset blocker does not discard earlier preview evidence.

MasterStore reads ordered pages of 100, requires stable exact counts and unique
identities, and blocks at 100,000 rows or truncated pages. A full dataset plan is
validated before the first mutation. Classifications: NEW, CHANGED, UNCHANGED,
SOURCE_MISSING, INVALID, CONFLICT; UNSUPPORTED is also explicit at capability level.
Unknown counts are null, not fabricated zero. Reports contain per-dataset mode,
source/capability/evidence/scope/pagination/mapping, source/canonical/validation and
change counts, identity-only classifications, planned/actual counts, readback,
safe error codes, warnings and recovery. Raw source bodies and DB exception text
are never printed. Actual counts mean acknowledged writes, not guessed commits.

Existing symbols retain status/intraday_status; existing index_master retains
status. Updates send only changed source-owned fields. New stocks explicitly
insert inactive/inactive; new indexes inactive. created_at is sent only for new
symbols; other tables receive application updated_at only when written. Generic
upsert_symbols/upsert_index_master defaults are deliberately unchanged.

Insert uses existing unique key with ignore_duplicates, then verifies returned
row and readback. A concurrent insert cannot overwrite local controls. Updates
use identity plus compare-and-set on changed descriptive columns, never status.
UNCHANGED is not rewritten. SOURCE_MISSING is absence from the source snapshot,
not confirmed delisting; no deletion/inactivation. Membership is never replaced.

**Atomicity: one row/request, no cross-table or whole-dataset transaction.**
Later failure preserves acknowledged counts and PARTIAL status. An ambiguous
write sets insert_counts_confirmed=false (also covers updates) and stops without
retry. Readback failure is explicit. No delete/rollback/cleanup is automatic.
Concurrent dataset reads are not a repeatable-read DB snapshot; count, identity
and compare-and-set guards fail closed on detected changes, but an owner should
avoid overlapping sync writers. Concurrency of operator status edits is allowed:
updates never send those fields or revert the operator's decision.

## Recovery and provider extension

On write/readback failure, stop; inspect the reported identity and current rows
read-only. Re-run DRY_RUN, review its plan, then explicitly rerun that one dataset
with --write only after source readiness is independently verified. Previously
completed identical records become UNCHANGED. No automatic ambiguous-write retry.

To add SSI v4/v5 (none implemented):

1. Capture redacted real endpoint envelopes, request contracts, field/type/board
   semantics and all paging/terminal/error evidence, independently per dataset.
2. Implement a version adapter/mapper using shared authentication and bounded
   retries. Never use a short page alone as completeness proof. Validate totals,
   repeated/wrong/changed pages, missing envelopes, caps and authoritative scope.
3. Return MasterSnapshot canonical DTOs; report missing/unsupported fields and
   safe distinct auth/HTTP/rate-limit/timeout/malformed/pagination errors.
4. Register explicit per-dataset MasterCapability in master_registry.py, initially
   BLOCKED/PREVIEW. READY requires evidence plus verified complete source contract;
   it is never inferred from version number or availability of daily adapters.
5. Add real-source fixture mapping/paging tests and independent canonical/store
   tests. Verify read-only against the source before separately authorizing READY.
   CLI, table names, canonical validation and store implementation remain intact.

## Owner read-only verification SQL

These statements are supplied only; not executed during this task.

```sql
select status,intraday_status,count(*) from public.symbols group by 1,2;
select status,count(*) from public.index_master group by 1;
select symbol,market,name,status,intraday_status,created_at
from public.symbols where symbol = 'SSI';
select * from public.securities where symbol = 'SSI';
select * from public.index_master where index_code = 'VNINDEX';
select * from public.index_components where index_code = 'VNINDEX' order by symbol;
select indexname,indexdef from pg_indexes where schemaname='public'
and tablename in ('symbols','securities','index_master','index_components');
```

## Audit, database impact and validation report — 26 October 2026

Before coding: inspected AGENTS, main, parser/dispatch/maintenance, legacy master
modules, DB status/upsert helpers, schema and all master-related migrations,
provider registry/client/adapter, inspector endpoint/selectors, shared scope,
master/retirement/inspector tests, existing source fixtures, bilingual root/CLI/
ingest/provider docs and repository-wide master references/workflows/scripts.
Root gap: disabled orchestration plus obsolete v2 field guesses; inspector
request definitions provide no valid source mapping. Generic master helpers
activate new rows by default and are unsuitable for sync-specific defaults.
Proposed/implemented files are inventoried below. No alternate legacy business
logic survives. Existing disabled check_complete_ssi_ingest script and unrelated
retired commands remain disabled. No workflow/schedule was enabled.

Tables reused: symbols, securities, index_master, index_components. Schema and
migration: NONE. Development rows touched: NONE. Existing data/control decisions
preserved. Price backfill: NONE. No downstream ingestion/features/research.
Production mapping is unresolved: **PARTIAL**, not production-ready sync.

Offline canonical tests are synthetic version-neutral fixtures, not real SSI
master payloads. Source pagination/mapping live validation is NOT_RUN/BLOCKED;
no live SSI request, Supabase read/write, migration or live write smoke was run.
Next step: obtain bounded redacted real v3 master response/paging evidence and
verify each dataset independently before implementing/promoting its mapper.

## Final validation and file inventory

Targeted: **91 passed**; full suite: **1115 passed, 7 skipped** (26.65s). Seven existing PostgreSQL integration tests require TEST_DATABASE_URL. Compile, both CLI help commands and diff whitespace check passed. Real PostgREST SDK query checks used httpx.MockTransport (no network).

```bash
.venv/bin/python -m pytest -q tests/ingest/test_versioned_master_sync.py tests/ingest/test_master_data_pipeline.py tests/cli/test_capability_retirement.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py sync-master-data --help
.venv/bin/python main.py init --help
git diff --check
```

Modified files:

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `src/README.md`
- `src/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/maintenance.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/master/index_master.py`
- `src/ingest/master/init_symbols.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/README.md`
- `src/providers/ssi/adapters/README.vi.md`
- `tests/cli/test_capability_retirement.py`
- `tests/ingest/test_master_data_pipeline.py`

Created files:

- `src/ingest/master/contracts.py`
- `src/ingest/master/store.py`
- `src/ingest/master/sync.py`
- `src/providers/ssi/adapters/master_v3.py`
- `src/providers/ssi/master_contract.py`
- `src/providers/ssi/master_registry.py`
- `tests/ingest/test_versioned_master_sync.py`

Deleted files: NONE. Removed legacy mapper bodies; import names retained as wrappers.
