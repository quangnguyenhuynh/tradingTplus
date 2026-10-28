# CLI documentation restoration audit

## Canonical EOD CLI — 28 October 2026

| Command | Existing behavior retained |
| --- | --- |
| `stock-eod` | Stock ingest + existing daily completeness; active-symbol filtering |
| `stock-eod-backfill` | Inclusive stock daily backfill; no added completeness |
| `index-eod` | Existing index daily raw/clean ingest |
| `index-eod-backfill` | Existing inclusive index daily backfill |

Only these four top-level names are supported for stock/index EOD ingest/backfill.
Removed (no aliases/redirects): `daily`, `stock-daily`, `stock-daily-backfill`,
`backfill-daily`, `index-daily`, `index-daily-backfill`, `index-backfill`.
Old direct daily had different date/scope/completeness semantics and is retired;
stock-eod retains run_stock_eod_pipeline rather than adopting daily_run behavior.
Stock/index EOD defaults resolve the latest weekday on/before today in Vietnam;
original date validation, scope rules, summaries and exit codes remain unchanged.
Backfill date aliases --from/--from-date and --to/--to-date remain available.
PARTIAL can still exit 0 under existing _status_to_exit; no exit-policy changes.
Internal daily_run/run_daily_ingest/run_index_daily_ingest/backfill imports,
stock_daily/index_daily dataset IDs and JSON flows (including index-daily,
backfill-daily/index-backfill) remain unchanged. Inspector `stock-daily` remains.
Stock/index pipelines stay separate; no automatic feature/signal/backtest.
No migration/schema/data changes or required backfill. Do not execute WRITE
examples to verify naming. Historical naming/alias reports below are superseded.

```bash
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
```


[Tiếng Việt](CLI_DOCUMENTATION_AUDIT.vi.md)

## Scope and pre-edit audit

Behavior reference: dev `b5cb3276f367a0e50ded3c83967570f24b7480c6` (PR #178). Historical documentation: `90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5`. The initial checkout was historical and origin/dev stale; git fetch failed because the proxy was unreachable. The GitHub connector verified current dev. Its snapshot was reconstructed from GitHub patches/objects and blob/tree/commit hashes verified before checking out docs/restore-cli-ssi-v3. No application changes were made to construct the snapshot; the documentation diff is relative to the exact dev commit.

The audit compared AGENTS, main/CLI parsers/handlers, provider capabilities/registry, active ingest/features/research entrypoints, scripts/parsers, bilingual README pairs, CURRENT_STATE, architecture decisions, restructure mapping, workflows, relevant schema/migrations and CLI/inspector tests. English retained a short command inventory; Vietnamese summarized status and referred readers to English. Scope/mode/side-effect/troubleshooting and foreign/research workflows were lost; generic package READMEs and moved relative links reduced usability.

Before editing, the chat reported the proposed self-contained bilingual runbooks, root/src/CLI/script/inspector/domain updates and this new audit pair, Markdown-only scope, migration none, data none, backfill none, and offline help/parser/planning/link/compile/test validation. No additional approval was needed within the authorized documentation scope.

## Historical example disposition

| Category | Examples / decision |
| --- | --- |
| Still valid | Clean-data daily/intraday feature date/range/full/replace; foreign preview/dry-run/check/rank/history; index preview/features; registered Analog/Screener syntax |
| Valid after adaptation | REST inspector moved to scripts/inspectors/ssi_rest with v3 selectors; checks/previews/maintenance/capture paths; domain links follow ingest/contracts/providers/features/research |
| Obsolete after retirement | Retired source options, REST URLs, consumer credentials and fallbacks; not restored as operational commands |
| Temporarily unavailable | Master sync/init, intraday source/backfill, combined backfill, refill, streaming/orderbook and dependent diagnostics |
| Incorrect/unverified | Literal [--apply] inside bash examples; stale disabled-command help; literal auto source; exit 0 interpreted as completeness; claimed Analog validation persistence; live readiness/completeness without evidence |

## Contradictions and separate code issues

1. daily defaults to the previous weekday; stock-eod/stock-daily/index-daily include today. Plain daily uses explicit symbols directly; EOD intersects active master scope.
2. Disabled-command help still describes former ingestion; preflight runtime is authoritative. Empty index_master errors suggest sync-master-data although sync is disabled.
3. scripts/previews/run_features.py writes stock_features without a dry-run/date flag; naming/location is misleading. The script was not moved or changed.
4. Direct streaming inspector execution shadows standard inspect with inspect.py and triggers a circular import. Module help works. Direct path is marked BLOCKED; operations remain NOT_IMPLEMENTED.
5. Analog validate accepts --apply but does not persist analog_validation_runs. A complete new validation/approval lifecycle cannot be claimed through CLI alone. Inspect requires --distance-threshold but runtime ignores it under top-k matching.
6. REST inspector still prints an old data_contracts mapping path; the actual file is under contracts. Zero page-index/page-size become defaults before validation.
7. check_ssi_ingest_schema retains some old index/foreign column expectations; fix the diagnostic separately rather than changing schema to satisfy obsolete fields.
8. Legacy intraday-value SQL has a broad unscoped close*volume update; it is not a safe production repair example.

## Restored operations and classifications

32 production commands, all Analog subcommands/alias, arguments/defaults/requirements/choices; stock/index ingestion/backfills; incremental/full/range/atomic-replace features; complete foreign preview/dry-run/check/ranking/history without a calendar dependency; Screener V1/V2 config/apply; Analog profile/history/validation/review/query/inspect/daily; native/alias/range/paging/mapping inspector workflows; 13 Python CLI scripts and one SQL artifact. Helper modules are not independent CLIs.

READ-ONLY SSI: REST inspector and index-preview. READ-ONLY DB: checks, feature preview/check, foreign RPC, screener preview and Analog reads/dry-runs (local profile dry-run needs no DB). WRITE: raw/clean ingestion, feature calculation, run_features, gated screener/config/Analog apply and atomic replacement. NOT_IMPLEMENTED: eight production commands and dependent diagnostics/capture/streaming. Feature replacement requires one symbol/timeframe/range; write examples were never executed for validation.

Changed local links were checked for existence and moved package/feature links corrected, preserving English/Vietnamese cross-links. Both main runbooks share argument/example coverage and are self-contained. Retired source operations and automatic production trading-signal claims were not restored.

## Validation and results

Used `.venv/bin/python`; initial system-Python attempts lacked the Supabase SDK/pytest. The existing venv supports the offline checks below; project dependency/configuration files were not changed.

```bash
.venv/bin/python main.py --help
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python -m pytest -q tests/cli tests/inspectors
.venv/bin/python -m pytest -q
.venv/bin/python work/validate_docs.py
git diff --check
```

- PASS: compileall and whitespace checks.
- PASS: CLI/inspector tests, 122 passed.
- PASS: full suite, 577 passed and 7 skipped (PostgreSQL atomic-replace tests require TEST_DATABASE_URL).
- PASS: 140 unique examples parsed offline, including feature scope/replacement and inspector request-plan/selector validation; no operational services invoked. Coverage includes 32 production commands and Analog subcommands/alias.
- PASS: changed Markdown local link targets exist; language pairs and main examples align.
- PASS: 62 of 63 help/list invocations, covering root/commands/subcommands, inspector list/run help and scripts with parsers. check_supabase has no help parser; its no-option syntax was checked without running DB access.
- Pre-existing FAIL, BLOCKED: direct-path streaming inspector help (ImportError/circular import); module help PASS. Source was not changed within this documentation-only task.
- SKIPPED by design: live SSI/Supabase reads/writes, production persistence/completeness, migration application and backfills. Parser success does not establish data availability or account entitlement.

The validation helper is scratch under work/, not part of the documentation patch. Packaging moves scratch to /workspace/work/tradingTplus-documentation; the command above records its location when executed.

## Modified files

- `README.md`
- `README.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `scripts/README.md`
- `scripts/README.vi.md`
- `scripts/capture/README.md`
- `scripts/capture/README.vi.md`
- `scripts/checks/README.md`
- `scripts/checks/README.vi.md`
- `scripts/inspectors/README.md`
- `scripts/inspectors/README.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_streaming/README.md`
- `scripts/inspectors/ssi_streaming/README.vi.md`
- `scripts/maintenance/README.md`
- `scripts/maintenance/README.vi.md`
- `scripts/previews/README.md`
- `scripts/previews/README.vi.md`
- `src/README.md`
- `src/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/diagnostics/README.md`
- `src/diagnostics/README.vi.md`
- `src/features/README.md`
- `src/features/README.vi.md`
- `src/features/foreign/README.md`
- `src/features/foreign/README.vi.md`
- `src/features/index/README.md`
- `src/features/index/README.vi.md`
- `src/features/stock/README.md`
- `src/features/stock/README.vi.md`
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
- `src/research/analogs/README.md`
- `src/research/analogs/README.vi.md`
- `src/research/screener/README.md`
- `src/research/screener/README.vi.md`

## Created files

- `docs/CLI_DOCUMENTATION_AUDIT.md`
- `docs/CLI_DOCUMENTATION_AUDIT.vi.md`

## Impact and next step

Migration: none. Database impact: none (no tables/indexes/rows changed). Backfill: none. Remaining risks are service permissions, deployed schema, live source/history quality not tested, and the separate code issues above. Next step: review the documentation patch; address streaming imports and Analog validation persistence in a separate code task before relying on blocked workflows.

## EOD naming implementation report — 28 October 2026

Base dev: `7a16dcd31b31600e8546b0b3f8288795f3c59cab`. Audited AGENTS/main/parser/dispatch, stock/index/backfill/shared scope runners, relevant schema/migrations, tests/docs/workflows. Removed direct daily with its different semantics; stock-eod retains the existing workflow. Updated parser/handlers and index workflow call-site; Python APIs, dataset IDs, Inspector stock-daily, JSON flows and all pipeline/data logic remain unchanged. Only intraday aliases normalize. All seven removed names reject with exit 2, without redirects.

CLI: **225 passed**; ingest: **291 passed, 3 skipped**; pipeline: **146 passed**; full: **1241 passed, 10 skipped** (38.84s). Ten existing PostgreSQL integration cases require local disposable TEST_DATABASE_URL. Compile/help/rejection/diff checks PASS. No lint configuration found. All validation offline; no live ingest/backfill, SSI request or Supabase mutation.

Migration/schema/data: NONE. Backfill required: NO. Main risk: external scripts using removed names must update; defaults, PARTIAL exit handling and runner flow labels intentionally stay as before. Next: review/merge PR then update any external invocation to the four canonical names.

```bash
.venv/bin/python -m pytest -q tests/cli/
.venv/bin/python -m pytest -q tests/ingest/
.venv/bin/python -m pytest -q tests/pipeline/
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q main.py src scripts tests
python main.py --help
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
git diff --check
```

Smoke legacy names: daily, stock-daily, stock-daily-backfill, backfill-daily, index-daily, index-daily-backfill, index-backfill, each with --help: expected exit 2. Canonical helps exit 0, no service access.

Modified files:

- `.github/workflows/index-eod-v2.yml`
- `README.md`
- `README.vi.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/CLI_DOCUMENTATION_AUDIT.md`
- `docs/CLI_DOCUMENTATION_AUDIT.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/index.py`
- `src/cli/maintenance.py`
- `src/cli/parser.py`
- `src/cli/stock.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/index_daily/README.md`
- `src/ingest/index_daily/README.vi.md`
- `src/ingest/maintenance/README.md`
- `src/ingest/maintenance/README.vi.md`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/ingest/workflows/README.md`
- `src/ingest/workflows/README.vi.md`
- `tests/cli/test_backfill_names.py`
- `tests/cli/test_capability_retirement.py`
- `tests/cli/test_cli_refactor.py`
- `tests/pipeline/test_stock_eod_workflow.py`

Created files:

- `tests/cli/test_eod_names.py`

Deleted files: NONE.
