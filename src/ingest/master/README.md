# Guarded SSI v3 master sync — symbols and securities

[Tiếng Việt](README.vi.md)

The versioned architecture from PR #186 is reused. SSI v3 **symbols** and
**securities** are READY for the guarded non-destructive refresh contract below.
**index_master** and **index_components** remain unchanged, unverified and BLOCKED.
READY means verified mapping plus validated three-board acquisition and guarded
persistence, **not strict authoritative market-universe completeness**.

## Source evidence, scope and completeness

[Owner evidence, 26–27 October 2026](../../../docs/SSI_V3_MASTER_EVIDENCE.md):
GET /api/v3/data/securitiesByBoard with board=HOSE, HNX, UPCOM returned unpaginated
JSON arrays of 793/410/851 rows (2,054 observed). These counts are historical
reference diagnostics, never required equality or permanent market totals.

Every run fetches each board separately through SSIV3Client, validates HTTP 200,
parses the complete response bytes, requires an array, checks every record's
identity/board/types/optional numeric/date fields, and rejects duplicate identities
within/across boards. No paging parameters are invented. All three boards must
succeed; no invalid record is silently skipped into a successful snapshot.
Symbols and securities share this exact fetch/mapper implementation; independent
CLI runs deliberately obtain independent current snapshots, with no global cache.

Reports distinguish full HTTP response parsing, successful board enumeration,
internal consistency and authoritative market coverage. pagination_complete means
complete acquisition of the declared three-board response scope, not a provider
market total. pagination.mode=UNPAGINATED_ARRAY; provider_reported_total=null;
authoritative_market_completeness=UNVERIFIED is always visible. No HTTP 200/parsed
array/count threshold can independently prove that SSI returned every security.

Conservative policy, before any mutation or SOURCE_MISSING classifications:

- Empty board, malformed/truncated body, wrong board, invalid/duplicate record,
  failed board, row/body limit or any source error blocks the whole dataset.
- A board count below 50% of the latest owner reference blocks with
  SOURCE_COUNT_REGRESSION. Counts may differ normally; no equality is required.
  Reference evidence must be updated only after separate source investigation,
  never by bypassing CLI validation. The threshold is an anomaly policy, not an
  estimated authoritative market size. Production has no force/override flag.
- A source universe or known DB market group below 50% of existing dataset counts
  blocks SOURCE_DB_COUNT_REGRESSION before mass missing conclusions. Count, board
  and securities security-type distributions/deltas are reported. The owner
  provided no historical type distribution; DB distribution is compared when
  available. Unknown types are retained and counted, not coerced or excluded.
- Source failures preserve board-level diagnostics and completed evidence, with
  no partial dataset write. Missing authoritative totals remain a residual risk
  even after every guard passes. Avoid overlapping sync writers.

Request bounds: three board data calls, at most three attempts each by default
(client hard cap five), shared auth, 30s per request, maximum 16 MiB parsed body
and 20,000 records/board. HTTP 429/5xx use bounded backoff; Retry-After up to 30s
is respected, longer/invalid waits fail safely instead of retrying early. Transport
truncation, JSON/non-finite/duplicate-key errors, auth, HTTP and rate-limit errors
have distinct safe codes. No credentials, tokens, auth bodies or full error bodies
are logged. No live SSI request was made by the agent in this task.

## Canonical mapping

| Source | symbols | securities |
| --- | --- | --- |
| symbol | symbol | symbol |
| board | market | market, exchange |
| symbolNameVi | name | stock_name |
| symbolNameEn | — | stock_en_name |
| stockType | — | sec_type |
| lotSize | — | lot_size |
| listedShare | — | listed_share |
| firstTradingDate | — | first_trading_date |
| lastTradingDate | — | last_trading_date |
| maturityDate | — | maturity_date |
| sanitized source object | — | raw |

Identifiers trim/uppercase, retain long bond identifiers, and obey the existing
canonical allowed characters/max 64. Boards must exactly match HOSE/HNX/UPCOM and
the requested board. Names preserve Unicode; absent/null/blank optional text,
numbers and dates become NULL. Nonempty invalid numeric/date values block both
datasets. Numeric strings and numeric JSON tokens are parsed without binary float;
dates YYYY/MM/DD or YYYY-MM-DD normalize to ISO. No zero/name/issuer/type fallback.
Zero stays zero. All Stock/Bond/ETF Product/Investment Fund/unknown/NULL types are
represented in both tables. Market existence does not imply T+ strategy eligibility.

securities.raw is a recursively sanitized JSON-compatible source copy. Secret
keys and configured credential values are redacted; unknown JSON-safe source
fields may remain raw-only. Exact JSON Decimal values use an integer when integral,
otherwise a decimal string for JSONB/SDK compatibility. No unknown field becomes
a schema column. issuer, issue_date and tick_price/tick_increment fields are not
sourced; report lists them unsupported and existing DB values remain intact.
Securities numeric DB columns are selected/cast to text for compare, write acknowledgements and readback, avoiding SDK binary-float decoding. Generic DB/price clients are unchanged.
Mapping version: ssi_v3.securitiesByBoard.1.0.0. Inspector symbol_list mapping now
populates stock_name/market/exchange/security_type using the verified names;
its PASS is row mapping only, not board/universe/persistence validation.

## CLI and database prerequisites

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --dry-run
python main.py sync-master-data --dataset securities --data-source ssi_v3 --dry-run
python main.py init --dataset symbols --data-source ssi_v3 --dry-run
```

SSI_API_KEY/SSI_API_SECRET and local Supabase service credentials are required to
fetch and compare. Dry-run performs zero mutations. Omitted source selects the
newest verified READY master provider for that dataset, currently ssi_v3 for these
two only. Explicit ssi_v2/v4/v5/auto is rejected, no fallback. The price registry
and all daily/intraday behavior remain unchanged.

Only after reviewing both dry-run reports, the owner may run:

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --write
python main.py sync-master-data --dataset securities --data-source ssi_v3 --write
```

--write requires exactly one explicit dataset. --dataset all --write and
command-only --write reject (exit 2); --dry-run/--write are mutually exclusive.
all/omitted dataset is preview-only and currently PARTIAL because indexes BLOCKED.
Only OK exits 0; PARTIAL/FAILED/BLOCKED/UNSUPPORTED exit 1.

Read-only catalog verification of TradingTPus_DS on 27 October 2026 confirmed
symbols_pkey(symbol), securities_pkey(symbol), numeric/date/JSONB descriptive
columns, symbol status checks, and **no securities→symbols foreign key**. Therefore
securities can sync independently; symbols-first is an operational recommendation,
not a hidden dependency or automatic write. No related rows are created outside
the selected dataset. Recheck deployed constraints if the owner changes schema.

## Persistence, controls and recovery

CLI → existing master registry → v3 adapter → MasterSnapshot → canonical validation
→ existing comparison → guarded MasterStore → readback → JSON. No rebuilt CLI or
second orchestrator. Generic SupabaseClient upsert defaults remain unchanged.

MasterStore reads ordered pages of 100 with stable exact counts, unique identities
and a 100,000-row bound. Complete dataset validation/retention/plan precedes the
first mutation. Only NEW/CHANGED write; UNCHANGED skips; SOURCE_MISSING never means
confirmed delisting and never deletes or marks inactive. No membership replacement.
Existing non-null descriptions are never overwritten by NULL. Existing symbols
retain status/intraday_status; inserts explicitly inactive/inactive. Source status
never controls eligibility. Existing index code/status behavior is unchanged.

Insert uses existing unique key and ignore_duplicates. Concurrent insert cannot
overwrite controls. Update sends changed source-owned fields with compare-and-set,
never status. timestamps are application controlled. Every acknowledgement and
readback is checked. Actual counts are acknowledged-only, distinct from planned.
**Transactions remain one row/request, not atomic across a dataset/tables.**
Partial or ambiguous failure stops, preserves acknowledged evidence and reports
PARTIAL/nonzero; insert_counts_confirmed=false also covers uncertain updates.
No ambiguous automatic DB retry, delete, rollback or cleanup. Inspect reported
identities read-only, rerun DRY_RUN, then owner explicitly reruns the same dataset.
Completed identical rows become UNCHANGED. DB reads are not repeatable-read across
pages; use one sync writer, while concurrent operator flag edits are preserved.

## Owner read-only checks

```sql
select status,intraday_status,count(*) from public.symbols group by 1,2;
select market,count(*) from public.symbols group by 1 order by 1;
select market,sec_type,count(*) from public.securities group by 1,2 order by 1,2;
select * from public.symbols where symbol='SSI';
select * from public.securities where symbol='SSI';
select conrelid::regclass,conname,pg_get_constraintdef(oid)
from pg_constraint where conrelid in ('public.symbols'::regclass,'public.securities'::regclass);
```

These owner data checks were supplied, not executed. Agent catalog and numeric-literal cast reads were
performed. Production rows written: NONE. No migration, schema change, price
backfill, feature/signal/backtest, workflow or schedule change.

## Extension and validation status

Future SSI v4/v5 needs its own real evidence, adapter/mapper and explicit per-dataset
registration. Canonical validation, store, tables and public CLI remain reusable.
MasterSnapshot.retention_policy is optional version-neutral comparison metadata,
not an SSI field in orchestration. No v4/v5 or index support is fabricated.

Audit base dev: d2211cb329dc0503661e43f11e7e7bd83cfc91a3 (merged PR #186). Reviewed
AGENTS/main/CLI, all master modules, client/registry, schema/master migrations,
actual catalog/constraints, inspector/mapping, fixtures/tests/workflows and bilingual
docs. Gap: v3 adapter stub and unverified inspector descriptions; no architecture
replacement needed. All schema fields fit. Updated files/inventory and final
commands/results are recorded below.

Implementation complete for guarded symbols/securities. Residual limitations:
no authoritative provider total, no full owner response archive, no agent live SSI
smoke (credentials absent), no production write verification. Fixtures use
representative values under owner-verified field contracts, not verbatim market
rows. Offline HTTP/SDK tests validate code, not a new live-source observation.
Next step: owner runs the two dry-runs, reviews board counts/type distributions,
NULLs/unsupported fields/plan and controls, then separately executes scoped writes.

## Final report — 27 October 2026

Status: **PARTIAL** overall verification; requested code and offline checks complete. Agent live SSI smoke and production write/readback verification NOT_RUN (no SSI credentials; production writes forbidden). Owner-verified source evidence is distinguished from representative offline samples. Capability READY is limited to the documented guarded refresh, with authoritative market completeness UNVERIFIED. Both index capabilities remain BLOCKED.

Targeted: **2 + 66 + 132 = 200 passed**. Full suite: **1222 passed, 7 skipped** (31.65s); existing PostgreSQL integration tests require TEST_DATABASE_URL. Compile, help and diff check passed. PostgREST SDK HTTP queries/decimal text casts verified offline; read-only PostgreSQL numeric literal cast returned exact decimal/large integer. No Supabase write or live SSI request.

Tables: symbols/securities only for future owner writes; actual development data writes NONE. Existing records/controls preserved, new inactive defaults, no migration/schema/backfill/schedule/downstream change. No files deleted; compatibility wrappers remain. Next: owner reviews both dry-runs then explicitly writes one dataset at a time.

```bash
.venv/bin/python -m pytest -q tests/ingest/test_master_data_pipeline.py
.venv/bin/python -m pytest -q tests/ingest/test_versioned_master_sync.py
.venv/bin/python -m pytest -q tests/ingest/test_ssi_v3_master_adapter.py tests/inspectors/test_ssi_api_mapping.py tests/data_preview/test_v3_client.py
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
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `src/README.md`
- `src/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/contracts/README.md`
- `src/contracts/README.vi.md`
- `src/contracts/mappings/ssi_v3.json`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
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
- `src/providers/ssi/clients/rest_v3.py`
- `src/providers/ssi/master_contract.py`
- `src/providers/ssi/master_registry.py`
- `tests/ingest/test_master_data_pipeline.py`
- `tests/ingest/test_versioned_master_sync.py`

Created files:

- `docs/SSI_V3_MASTER_EVIDENCE.md`
- `docs/SSI_V3_MASTER_EVIDENCE.vi.md`
- `tests/fixtures/data_preview/ssi_v3_master_contract_samples.json`
- `tests/ingest/test_ssi_v3_master_adapter.py`

Deleted files: NONE.
