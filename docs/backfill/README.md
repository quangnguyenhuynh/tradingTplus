# Source-data backfill CLI

[Tiếng Việt](README.vi.md) · [CLI reference](../CLI_USAGE.md)

## Canonical names and compatibility

Source-data backfill names use `<dataset>-backfill`. Legacy aliases remain supported without a removal date. Argparse preserves the invoked spelling; CLI dispatch normalizes the three canonical spellings to existing handler keys. Python modules, public runner names, arguments, algorithms, status/exit behavior and JSON `flow` identifiers do not change. No deprecation text is printed to stdout.

| Canonical CLI | Compatible alias | Current behavior / existing runner |
| --- | --- | --- |
| `stock-daily-backfill` | `backfill-daily` | ACTIVE / WRITE → `run_daily_backfill_pipeline()` |
| `stock-intraday-backfill` | `backfill-intraday` | DISABLED / NOT_IMPLEMENTED before handler access |
| `index-daily-backfill` | `index-backfill` | ACTIVE / WRITE → `run_index_backfill_pipeline()` |

## Active source-data commands

The examples below write raw/clean data and are for an explicitly authorized operator scope, not offline verification. Stock uses `--symbols`; index uses `--indexes`. Date aliases `--from-date`/`--to-date`, optional `--data-source`, required date bounds, scope defaults and validation remain identical. There are no new `--write`/`--dry-run` flags.

```bash
python main.py stock-daily-backfill --from 01/10/2026 --to 20/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py index-daily-backfill --from 01/10/2026 --to 20/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
```

Daily stock backfill uses SSI v3 `securitiesSummary` and writes `stock_raw_daily`/`stock_daily` only. Index Daily uses SSI v3 `indexSummary`, existing index-master resolution, and `index_raw_daily`/`index_daily`. Explicit unsupported sources (including ssi_v2) remain rejected; there is no fallback. Both retain their existing inclusive date handling, future/reversed-range rejection, sequential processing, weekend skipping/reporting and weekend-only OK no-op. Per-date exceptions remain recorded and later dates continue. They do not calculate features, run completeness automatically, or trigger signals/backtests.

Stock symbols are trimmed, uppercased and deduplicated in first-seen order. Index scope is trimmed/deduplicated case-insensitively while preserving first spelling, then resolved using the existing persisted master. Omitted scope keeps existing master behavior. Empty explicit scope is invalid. Daily JSON keeps `flow=backfill-daily` and day flow `backfill-daily-day`; index JSON keeps `flow=index-backfill` and day flow `index-backfill-day`. Exit 0 for OK/PARTIAL, 1 for FAILED/runtime failure, 2 for invalid arguments/source, as before.

## Disabled routes and manual pilot boundary

`stock-intraday-backfill` and `backfill-intraday` are reserved names only. Both produce controlled FAILED/NOT_IMPLEMENTED JSON and exit 1 without loading handlers, SSI/Supabase clients, manual ingest or feature code. Explicit ssi_v3 is checked against stock_intraday in preview lookup without adapter construction, then remains blocked; unsupported sources keep exit 2. No new readiness or workflow is enabled. Inspect help only:

```bash
python main.py stock-intraday-backfill --help
python main.py backfill-intraday --help
```

Combined `backfill`, `refill`, `intraday-ingest`, streaming-ingest and master commands remain disabled. Earlier runbooks describing combined orchestration/refill execution or supported legacy SSI v2 are superseded by this current availability statement. The deprecated Python `backfill(...)` compatibility wrapper still delegates to the unavailable combined pipeline; it is not an active replacement for split daily backfill.

The separately guarded `stock-intraday` single-symbol/day pilot is unchanged and is not a backfill alias. Never route the reserved range command through that pilot. Source-data backfill does not rename or alter `features`, `features-daily`, `features-intraday`, `foreign-features-backfill` or `index-features-backfill`; feature rebuild/backfill is an independent pipeline.

## Offline verification and impact

Help for all canonical and legacy names needs no credentials and executes no services:

```bash
python main.py --help
python main.py stock-daily-backfill --help
python main.py backfill-daily --help
python main.py index-daily-backfill --help
python main.py index-backfill --help
```

No schema/table/data migration, historical change or backfill is required by the naming change. No workflow schedule changes or production runs are part of this task. Preserve existing raw/clean/validation/features behavior; do not repair historical data just to rename CLI entrypoints.

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
