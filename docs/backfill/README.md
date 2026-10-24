# Guarded source-data backfill

[Tiếng Việt](README.vi.md)

## Naming and availability

| Canonical | Alias | Status |
| --- | --- | --- |
| `stock-daily-backfill` | `backfill-daily` | ACTIVE / WRITE unchanged |
| `stock-intraday-backfill` | `backfill-intraday` | GUARDED_OPERATOR / DRY_RUN by default |
| `index-daily-backfill` | `index-backfill` | ACTIVE / WRITE unchanged |

Daily/index runners, JSON flows and write-by-default semantics stay unchanged; no write/dry-run flags are added to those routes. Feature backfill remains separate and unchanged.

```bash
python main.py stock-daily-backfill --from 01/10/2026 --to 20/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py index-daily-backfill --from 01/10/2026 --to 20/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py stock-intraday-backfill --help
python main.py backfill-intraday --help
```

## Guarded operator intraday backfill

`stock-intraday-backfill` (compatible alias `backfill-intraday`) now runs the existing guarded manual pilot sequentially for an explicit inclusive range and explicit symbols. Default is **DRY_RUN**; only `--write` persists. `--dry-run`/`--write` are mutually exclusive. Dates accept DD/MM/YYYY or YYYY-MM-DD and keep --from-date/--to-date aliases. No ALL/wildcards/comma scopes, implicit universe, future/inverted ranges or force overwrite. Normalize/deduplicate symbols in input order; process dates ascending and symbols in that order. Reject more than **50 symbol/weekday pairs** before services. Weekends skip without calls; a weekend-only range is an OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Owner only, after reviewing the dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Each pair reuses `run_manual_intraday()` eligibility (both persisted statuses active), SSI v3 whole-day pagination/mapping/value validation, exact Vietnam-day UTC conflict preflight, raw-first insert-only persistence and scoped readback. No SSI v2, timestamp repair, value estimate, batch filtering or conflicting overwrite. Preserve raw source JSON/hash and exact BIGINT `ohlc.value`; completeness stays UNVERIFIED, with no 226-bar requirement. A valid empty source is NO_SOURCE_DATA, not a verified holiday or success. Unsupported historical dates and invalid batches remain explicit failures. Dry-run performs zero mutations/partition RPCs and reports actual inserts=0 with separate planned counts; absent DB preflight is BLOCKED, never write-ready.

Ordinary pair conflicts/source validation errors continue safely; systemic configuration/auth/exhausted shared-dependency errors halt with completed and unprocessed scopes reported. No automatic retry of ambiguous DB writes. Pair PARTIAL retains raw commits, acknowledged counts and recovery; inspect exact scope read-only, resolve the cause, then explicitly rerun. Identical rows skip and missing clean can be completed under the existing guards; no cleanup/delete or cross-table atomicity claim. Range OK requires every planned pair verified (or no work); mixed verified success/failure is PARTIAL; no verified success with failures is FAILED, even when a pair committed partial raw data. Per-pair PARTIAL/insert counts remain visible in that FAILED range. CLI exits 0 only for OK, 1 for any non-success/unverified range, 2 for invalid scope/source/arguments. Other CLI exits are unchanged.

Range JSON retains `flow=backfill-intraday`, reports planned/processed/OK/blocked/partial/failed/no-source pairs, totals, planned inserts, halted/unprocessed scopes and full pilot summaries in per_symbol_date. Only summaries survive each pair; raw/clean working batches are released. Registry remains preview with no generic intraday production factory. Single-symbol/day stock-intraday is unchanged; intraday-ingest, combined backfill, refill, master and streaming stay disabled. No automatic feature/completeness/signal/backtest/alert stage. Workflow stock-intraday remains disabled and unscheduled. No migration or development backfill; Codex performs no live writes. See [manual pilot runbook](../STOCK_INTRADAY_PIPELINE.md) for operator recovery and post-write read-only checks.

## Post-write read-only verification

Owner retains dry-run/write/rerun JSON; require all pairs OK, insert_counts_confirmed=true and per-pair WRITE consistency_status=PASS; repeated actual inserts should be zero. Review conflicts/failed_stage/recovery, never force historical repair. Legacy timestamps/value/provenance stay untouched. Raw key `(symbol,time,data_hash)` and clean `(symbol,timeframe,time)` are unchanged. Historical raw hashes may coexist under the existing pilot policy; matching existing clean rows are never relabeled as proven SSI provenance. Preflight/insert/readback is per pair, not a transaction over the range or both tables. Without DB preflight the source preview cannot approve writes and the range blocks/halts. Unknown pair plans make aggregate planned counts NULL, never fabricated zero.

```bash
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/check_ingest.py --date 21/10/2026 --symbols SSI HPG
```

Completeness OK covers structural checks only, not every SSI market minute. Empty data is not holiday proof. Unsupported historical dates retain NO_SOURCE_DATA/error without v2 fallback. Deployment needs no migration or automatic historical rerun; owners choose --write scopes after review. Bar-start/end and independent turnover semantics receive no new certification in this task.

## Implementation report — 2026-10-24 guarded intraday range

**Status: COMPLETE (implementation and feasible offline verification). Operator production-range verification remains pending.** Base dev rechecked at `89acaef907b34d7b2df966d4172900035f3b044d` (PR #184). Previously both intraday backfill spellings and the runner were unavailable. The owner-authorized manual pilot already had the required source, eligibility, validation, insert-only and readback protections; this task adds bounded orchestration over it, not a second ingest service.

Call flow: canonical/legacy parser → existing name normalization → scoped preview-source lookup → maintenance handler → run_intraday_backfill_pipeline → run_manual_intraday for each explicit pair → existing SSI v3 preview adapter/client/mapper/validator → existing guarded raw-first/clean/readback boundary only in WRITE. Dates/symbols/work count are validated before any client or source request; weekdays are counted arithmetically before bounded enumeration. At most 50 pairs, ascending dates then normalized first-seen symbols, no parallelism/background work. The report preserves legacy flow=backfill-intraday and existing public runner arguments, adding keyword-only write=False. Other commands' exit rules remain unchanged; this route alone exits nonzero for partial/unverified work.

The stable pilot's persistence/mapping behavior is unchanged. Necessary additive metadata includes source/validation status, sanitized error category and systemic flag; absence of DB configuration is labeled before fetch so even empty/source-failed dry-runs cannot approve or continue an invalid global plan. Range classification distinguishes valid EMPTY from failed paging, adds NO_SOURCE_DATA without holiday inference, and turns source-only OK into blocked/unverified preflight. Systemic auth/config/shared dependency errors halt and identify remaining NOT_RUN scopes; ordinary source validation/unsupported dates/conflicts continue. No new HTTP or DB retry loop; ambiguous DB outcomes require explicit safe rerun. No raw/clean working batch is retained between pair calls.

Both aliases share explicit required --symbols and inclusive --from/--to (legacy date-option aliases kept), accept DD/MM/YYYY/ISO, default DRY_RUN and mutually exclusive --write/--dry-run. SSI v3 is explicit on the actual pilot call, even when source option is omitted. ALL/wildcards/comma/blank/malformed symbols, future/reversed dates, unsupported source, nonboolean programmatic write and oversized plans reject before services. Weekend-only is an OK zero-work no-op, not write approval. No force flag or implicit active-symbol expansion.

Raw/clean safety, source time and value contracts remain those of the verified pilot: exact aware market instants/seconds normalized to UTC, exact source BIGINT value, original JSON/stable semantic hash/source ssi_v3, both master statuses active, whole-date paging from page 1, no rejected subset, duplicates or mixed order. Raw key (symbol,time,data_hash) and clean key (symbol,timeframe,time) are unchanged, 1m only. Identical rows skip; raw source/payload/key or canonical clean differences/unexpected timestamps block. Legacy timestamps/provenance are never shifted/repaired. Partition RPC is write-only after validation/preflight, for required months only. Raw is confirmed before clean; final scoped consistency readback is retained. No global production-ready registry promotion, feature calculation, automatic completeness stage, signal/backtest/alert or scheduled workflow.

### Verification

```bash
.venv/bin/python -m pytest -q tests/cli/test_backfill_names.py
.venv/bin/python -m pytest -q tests/cli/test_capability_retirement.py
.venv/bin/python -m pytest -q tests/cli/test_manual_intraday_cli.py
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py
.venv/bin/python -m pytest -q tests/pipeline/test_backfill_pipeline.py
.venv/bin/python -m pytest -q tests/pipeline/test_intraday_backfill.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
git diff --check
.venv/bin/python main.py stock-intraday-backfill --help
.venv/bin/python main.py backfill-intraday --help
```

Final individual suites: backfill CLI names **74 passed**, disabled capability **23 passed**, manual CLI **19 passed**, manual persistence **54 passed**, existing backfill pipeline **9 passed**, new range pipeline **74 passed**. Final full suite: **1049 passed, 7 skipped**. Compile/help/diff checks passed. An earlier full run before the final missing-DB/empty-source edge case was 1048 passed/7 skipped. Existing PostgreSQL replacement-RPC tests require TEST_DATABASE_URL and remain skipped; no disposable database or production write smoke was used. No live SSI/Supabase read smoke was required or run for this task; source and database integration used only fakes.

The new focused module reuses the pilot's fake SSI/PostgREST patterns and tests actual manual execution behind the range wrapper, not a duplicate ingest implementation. Coverage includes multi-symbol/date deterministic order, normalization, exact 50-pair boundary, huge-range rejection, weekends/no-op, explicit empty/unsupported data, auth/shared dependencies, unverified DB preflight, dry-run zero writes/RPCs, both eligibility controls, exact UTC scope/BIGINT/source JSON, duplicates/mixed/pagination/value guards, legacy conflicts/unexpected timestamps, partial raw-before-clean failure and explicit idempotent recovery, totals/JSON/exits, unrelated scopes and no downstream calls. Retired intraday cases were moved from disabled expectations to positive guarded routing and these safety tests; combined/refill/other disabled coverage remains.

### Files modified

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/maintenance.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/maintenance/backfill.py`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/stock_intraday/manual.py`
- `src/ingest/streaming/README.md`
- `src/ingest/streaming/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `tests/cli/test_backfill_names.py`
- `tests/cli/test_capability_retirement.py`
- `tests/pipeline/test_backfill_pipeline.py`

### Files created

- `tests/pipeline/test_intraday_backfill.py`

### Database impact and remaining risks

Migration/schema/contracts: **NONE**. Existing production data changed during development/testing: **NONE**. No historical backfill was run or required automatically by deployment. Operator-approved --write later may insert verified rows into the existing two tables and create their needed monthly partitions via the existing RPC. Conflict data remains unchanged; no deletion, replace, cleanup or historical relabeling. No feature formula/backfill change. Daily and index backfill remain unchanged.

**No live SSI production ingestion or Supabase database writes occurred during implementation or verification.**

Runtime still depends on source historical availability, active master statuses, valid local credentials, deployed unique constraints/RPC permissions and compatible partition settings. SSI empty weekdays are not certified holidays; source bar-start/end, independent turnover semantics and full market coverage remain UNVERIFIED. Other writers can change evidence after readback; choose a quiet operator window. Separate raw/clean calls and pairs are not a transaction over the range. When raw partly commits but no pair fully succeeds the range is FAILED with partial_pairs/raw_inserted/insert_counts_confirmed and recovery explicitly visible. A failed request may have committed additional rows beyond acknowledged counts. Do not rerun until reviewing exact scope/conflicts; then same-scope insert-ignore rerun can fill clean safely. Unknown/unprocessed plans keep aggregate planned insert counts NULL.

### Operator commands and next step

Use the dry-run example above first. Only the owner after reviewing every pair's preflight may execute the explicit --write example. Save dry-run/write/rerun JSON, require every pair OK and confirmed WRITE readback PASS, and verify repeated inserts are zero. Run the read-only Phase 0/completeness examples above; structural OK does not certify all market minutes. Do not activate symbols or repair legacy conflicts implicitly. Next step is owner validation of a small populated historical scope and safe rerun after merge; unattended/incremental/scheduled work needs a separate task. No production execution by Codex is authorized here.

> The naming report below is historical (2026-10-23). Its disabled intraday state is superseded by the guarded operator contract above.

## Implementation report — 2026-10-23

**Status: COMPLETE.** Base dev rechecked at `d81e0eff1bb63c7234c3a2c10cdfd88ace29ef17` (PR #183). The original CLI mixed prefix-style stock backfill names and index-backfill; all now have dataset-first canonical names with existing aliases preserved. Older backfill docs incorrectly advertised disabled intraday/combined/refill execution and explicit SSI v2 support; the current runbook above corrects these descriptions without changing code availability.

Exact implementation: parser registers canonical names with argparse aliases and existing argument actions/defaults unchanged. Main CLI normalizes only stock-daily-backfill → backfill-daily, stock-intraday-backfill → backfill-intraday and index-daily-backfill → index-backfill before source preflight/disabled checks/dispatch. Existing maintenance/index handlers and public runners are unchanged. No ingestion/API/DB/validation/feature/backfill algorithm code is modified; existing JSON flow and exit conventions are retained, with no stdout deprecation warning.

Explicit intraday-backfill source preflight now resolves stock_intraday rather than stock_daily, using nonproduction capability lookup without adapter construction. Supported ssi_v3 still reaches the controlled NOT_IMPLEMENTED/exit 1 guard; unsupported ssi_v2 remains exit 2. Without source it still blocks before handler loading. Both names remain unavailable, and combined backfill/refill/intraday-ingest/streaming-ingest remain blocked. Manual stock-intraday pilot, feature commands, registry readiness and workflow schedules are unchanged. Canonical/legacy daily and index routes call identical runners with identical dates/source/default scope; stock/index normalization differences remain intact.

### Tests executed and results

```bash
.venv/bin/python -m pytest -q tests/cli/test_cli_refactor.py
.venv/bin/python -m pytest -q tests/cli/test_capability_retirement.py
.venv/bin/python -m pytest -q tests/pipeline/test_backfill_pipeline.py
.venv/bin/python -m pytest -q tests/ingest/test_index_daily_pipeline.py
.venv/bin/python -m pytest -q tests/cli/test_backfill_names.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py --help
.venv/bin/python main.py stock-daily-backfill --help
.venv/bin/python main.py stock-intraday-backfill --help
.venv/bin/python main.py index-daily-backfill --help
.venv/bin/python main.py backfill-daily --help
.venv/bin/python main.py backfill-intraday --help
.venv/bin/python main.py index-backfill --help
git diff --check
```

The four required existing suites passed **25 / 25 / 10 / 16** respectively; the capability suite includes an extra canonical disabled-name case. New naming/routing/help/documentation tests: **74 passed**. Full regression: **978 passed, 7 skipped**. Compile, diff checks and all seven help invocations passed offline. Existing PostgreSQL replacement-RPC integration tests were skipped because TEST_DATABASE_URL is unset. No live backfill, source fetch or DB verification was attempted: active runners were faked and service/client/manual-pilot access guarded. Initial new-test assumptions about alias help wrapping and index spelling were corrected against existing behavior; final tests pass.

The new tests cover canonical and legacy parser arguments/date-option aliases, required bounds/invalid flags, source datasets/rejection, omitted scopes/source, exact runner arguments and JSON flows, unchanged OK/PARTIAL/FAILED exits, credential-free help and intraday blocking before handler/manual-pilot/API/DB access. Existing CLI, manual pilot, Daily/Index/features, disabled-capability and backfill regressions remain passing.

### Files modified

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/streaming/README.md`
- `src/ingest/streaming/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `tests/cli/test_capability_retirement.py`

### Files created

- `tests/cli/test_backfill_names.py`

### Database impact, risks and next step

Migration/schema/table/data changes: **NONE**. Backfill required: **NO**. No migration executed. No Python ingestion modules, provider/DB/feature logic or workflow files changed; only their affected bilingual README references were updated. Historical architecture decisions and earlier evidence reports retain their old spellings as historical/compatible aliases.

**No live SSI ingestion or Supabase database writes were executed.**

Remaining intentional limitations: intraday backfill is a reserved unavailable name, not an implementation; JSON flow identifiers retain legacy spelling and must not be inferred from the new CLI spelling. Active daily/index commands still write by default under their existing contracts and have no newly added dry-run/write switch. Live backfill was explicitly excluded, not reported as verified. Next step: review/merge this naming-only PR, prefer canonical help/examples in future operator instructions, retain aliases, and require a separate authorization/task before implementing intraday range ingest. No production rerun is needed to adopt the names.
