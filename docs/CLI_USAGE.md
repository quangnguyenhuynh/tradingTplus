# TradingTPlus CLI operational runbook — SSI v3

## Guarded operator intraday backfill

`stock-intraday-backfill` (compatible alias `backfill-intraday`) now runs the existing guarded manual pilot sequentially for an explicit inclusive range and explicit symbols. Default is **DRY_RUN**; only `--write` persists. `--dry-run`/`--write` are mutually exclusive. Dates accept DD/MM/YYYY or YYYY-MM-DD and keep --from-date/--to-date aliases. No ALL/wildcards/comma scopes, implicit universe, future/inverted ranges or force overwrite. Normalize/deduplicate symbols in input order; process dates ascending and symbols in that order. Reject more than **50 symbol/weekday pairs** before services. Weekends skip without calls; a weekend-only range is an OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Owner only, after reviewing the dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Each pair reuses `run_manual_intraday()` eligibility (both persisted statuses active), SSI v3 whole-day pagination/mapping/value validation, exact Vietnam-day UTC conflict preflight, raw-first insert-only persistence and scoped readback. No SSI v2, timestamp repair, value estimate, batch filtering or conflicting overwrite. Preserve raw source JSON/hash and exact BIGINT `ohlc.value`; completeness stays UNVERIFIED, with no 226-bar requirement. A valid empty source is NO_SOURCE_DATA, not a verified holiday or success. Unsupported historical dates and invalid batches remain explicit failures. Dry-run performs zero mutations/partition RPCs and reports actual inserts=0 with separate planned counts; absent DB preflight is BLOCKED, never write-ready.

Ordinary pair conflicts/source validation errors continue safely; systemic configuration/auth/exhausted shared-dependency errors halt with completed and unprocessed scopes reported. No automatic retry of ambiguous DB writes. Pair PARTIAL retains raw commits, acknowledged counts and recovery; inspect exact scope read-only, resolve the cause, then explicitly rerun. Identical rows skip and missing clean can be completed under the existing guards; no cleanup/delete or cross-table atomicity claim. Range OK requires every planned pair verified (or no work); mixed verified success/failure is PARTIAL; no verified success with failures is FAILED, even when a pair committed partial raw data. Per-pair PARTIAL/insert counts remain visible in that FAILED range. CLI exits 0 only for OK, 1 for any non-success/unverified range, 2 for invalid scope/source/arguments. Other CLI exits are unchanged.

Range JSON retains `flow=backfill-intraday`, reports planned/processed/OK/blocked/partial/failed/no-source pairs, totals, planned inserts, halted/unprocessed scopes and full pilot summaries in per_symbol_date. Only summaries survive each pair; raw/clean working batches are released. Registry remains preview with no generic intraday production factory. Single-symbol/day stock-intraday is unchanged; intraday-ingest, combined backfill, refill, master and streaming stay disabled. No automatic feature/completeness/signal/backtest/alert stage. Workflow stock-intraday remains disabled and unscheduled. No migration or development backfill; Codex performs no live writes. See [runbook](backfill/README.md) for operator recovery and post-write read-only checks.

Canonical CLI names and compatible legacy aliases (no removal date): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`; `index-daily-backfill` → `index-backfill`. Compatible CLI spellings remain; daily/index behavior is unchanged. Intraday uses the guarded operator range contract. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is guarded operator-only, DRY_RUN by default, with explicit --write and at most 50 weekday pairs; unattended routes remain disabled.

[Tiếng Việt](CLI_USAGE.vi.md)


## Guarded manual intraday pilot

`stock-intraday` now supports exactly one explicit symbol and Vietnam trading date. Default/`--dry-run` is READ-ONLY; only `--write` authorizes the guarded raw → clean insert sequence. SSI credentials are needed; Supabase service credentials enable read-only eligibility/conflict preflight and are required for writes. Without DB configuration, dry-run reports `NOT_RUN_NO_CREDENTIALS`, unknown planned counts and `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

The second command is **owner-only after reviewing dry-run/preflight**. No ranges, ALL/wildcards, omitted scope, multiple symbols or future dates. Both persisted master statuses must be active. Source is only `ssi_v3`, timeframe only `1m`; canonical value is exact `ohlc.value`, with missing/invalid values blocking this pilot and no estimation fallback. Identical existing rows are skipped; differing canonical clean rows or raw key/source/payload conflicts block. No force overwrite. Raw is confirmed before clean; a partial/ambiguous write exits nonzero and requires scoped inspection then a safe rerun. Cross-table atomicity is not promised. Completeness remains UNVERIFIED. Unattended intraday-ingest, combined backfill, refill, streaming and the schedule remain disabled. Features/signals/backtests never run from this pilot.

See [runbook](STOCK_INTRADAY_PIPELINE.md) for sequence, idempotency, partition behavior, recovery and owner verification. The inspector remains entirely read-only; registry readiness remains preview, with no generic production factory.

## Introduction and capability status

Verified against `dev` commit `b5cb3276` (PR #178). Run from the repository root. Examples use illustrative dates and symbols; check source availability and choose the exact intended scope before executing. Syntax was checked offline, not against live SSI or Supabase.

SSI v3 Stock Daily (`securitiesSummary`) and Index Daily (`indexSummary`) ingestion are ACTIVE. Stock, foreign and index features are ACTIVE on persisted clean data. Screener and Historical Analog are RESEARCH_ACTIVE. Intraday source ingestion, master synchronization, streaming and orderbook capture are NOT_IMPLEMENTED. The retired source has no fallback.

READ-ONLY — database read means no writes but still requires database access. READ-ONLY — SSI API request can make live requests without using Supabase. WRITE labels identify persistence, including explicit apply and scoped replacement. UNSUPPORTED means an input or operation is rejected, not an empty successful result.

## Installation and configuration

Use Python 3.11, matching CI. Install runtime requirements and pytest separately. Copy `.env.example` only for a new local configuration; fill credentials locally and never commit them. `src/config.py` loads `.env` with python-dotenv.

| Work | SSI credentials | Database credentials |
| --- | --- | --- |
| Daily ingest/backfill | `SSI_API_KEY`, `SSI_API_SECRET` | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (server-side) |
| REST inspector / index-preview | Same SSI pair | None |
| Feature calculation, checks, foreign RPC, screener, Analog DB workflows | None | Supabase URL and server-side key |
| Help, inspector list, config preview, Analog profile registration dry-run | None | None |
| PostgreSQL catalog check | None | `PHASE0_DATABASE_URL` |

The database client uses `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`; `SUPABASE_KEY` remains a configuration field but is not a fallback in this client. Use the service key for server operations and atomic replacement. Existing schema/RPC migrations must already be deployed for the chosen domain. This documentation task does not apply them.


```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
```


## Help and conventions

`--help` parses options and exits without running a service. Space-separate stock symbols; normalization trims, uppercases and deduplicates. Explicit empty symbol scopes are invalid. Index ingest/check/features use space-separated index codes and preserve canonical casing from `index_master`; index-preview alone takes one comma-separated string. All date ranges below are inclusive.

Stock source, stock features, foreign and index flows accept `DD/MM/YYYY` or `YYYY-MM-DD`; Analog dates require `DD/MM/YYYY`. The Phase 0 reconciliation script requires ISO dates. Interpret sessions in `Asia/Ho_Chi_Minh`; keep stored market timestamps timezone-aware. A weekday is not proof of a trading session.


```bash
python main.py --help
python main.py stock-eod --help
python main.py analogs --help
python scripts/inspectors/ssi_rest/inspect.py run --help
```


## Quick-start workflows

Start with read-only SSI preview. Source ingestion requires existing master data: master sync is disabled, so an empty installation cannot bootstrap itself with `init`. After validating the ingest summary, calculate features explicitly. Each command below is independent; stop and inspect its result before continuing.

The preview is READ-ONLY — SSI API request. Stock EOD is WRITE — raw/clean ingest. Daily features are WRITE — feature calculation. Screener defaults to READ-ONLY — database read. Do not execute all writes merely to test documentation.


```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
```


## Stock Daily ingestion

`daily` is WRITE — raw/clean ingest only. It fetches SSI v3 `securitiesSummary`, retains source payload/hash in `stock_raw_daily`, validates and persists canonical `stock_daily`. It does not run completeness or downstream calculations. No date means the latest weekday strictly before today in Vietnam. Explicit symbols are used directly; omitted symbols load active persisted master symbols.

`stock-eod` and its exact alias `stock-daily` are WRITE — raw/clean ingest plus daily-only completeness. They intersect explicit symbols with active master symbols and report ignored unknown/inactive values. Empty active scope returns FAILED. Their default date is the latest weekday on or before today in Vietnam, unlike `daily`. Completeness checks the current run timing and expected source. Neither route ingests indexes/intraday, writes a separate foreign-trading dataset, or starts features. Deprecated intraday counts/summary do not indicate an intraday operation.

Explicit weekend/future source-write dates are rejected. An empty holiday response is reported; rows are never synthesized. Both SSI and Supabase credentials are required.


```bash
python main.py daily --help
python main.py stock-eod --help
python main.py stock-daily --help
python main.py daily 19/10/2026 --symbols SSI
python main.py daily 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py daily --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-daily 19/10/2026 --symbols SSI HPG
```


## Stock Daily historical backfill

WRITE — raw/clean ingest: `stock-daily-backfill` requires `--from` and `--to`; `--from-date` and `--to-date` are aliases. Optional symbols apply to every included date; omitted means active master scope per ingest. Optional `--data-source ssi_v3` makes selection explicit; omission selects the ready v3 adapter, not the literal value `auto`.

The runner skips weekends, rejects future/reversed ranges, records per-day OK/PARTIAL/FAILED and continues across failures. Weekend-only ranges are OK no-ops. It does not verify completeness: inspect daily summaries and perform a separately scoped read-only check. Reruns may update existing clean rows and retain raw evidence. It does not calculate features or call the disabled combined backfill.


```bash
python main.py stock-daily-backfill --help
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```


## Index Daily preview and ingestion

`index-preview` is READ-ONLY — SSI API request; it never reads or writes DB rows. Required: either `--date` or `--from` together with `--to`, and comma-separated `--indexes`. Default output is a normalized table; `--raw` displays raw JSON, `--json` normalized JSON; these flags are mutually exclusive. No production `--data-source` option exists here.

`index-daily` is WRITE — raw/clean ingest from SSI v3 `indexSummary` into `index_raw_daily`, then validated `index_daily`. Optional positional date defaults to the latest weekday on/before today in Vietnam. `--indexes` takes one or more space-separated values. Omitted indexes select active `index_master`; explicit values must exist in master (explicit selection can include inactive rows). Empty master or unknown code raises ValueError, normally CLI exit 2. The error text suggests sync-master-data, but that command is disabled: inspect the persisted master and resolve it in separately authorized maintenance. Preview remains available without master data.


```bash
python main.py index-preview --help
python main.py index-daily --help
python main.py index-preview --date 2026-10-19 --indexes VNINDEX --raw
python main.py index-preview --from 2026-10-01 --to 2026-10-19 --indexes VNINDEX,HNXINDEX --json
python main.py index-daily 19/10/2026 --indexes VNINDEX HNXINDEX --data-source ssi_v3
python main.py index-daily 19/10/2026
```


## Index Daily backfill and completeness

`index-daily-backfill` is WRITE — raw/clean ingest, with required inclusive `--from`/`--to` (aliases `--from-date`/`--to-date`), optional master-backed `--indexes`, and optional source. It skips weekends and reports day/index counts; no feature calculation follows automatically.

`index-check` is READ-ONLY — database read of raw/clean coverage for an optional positional date and master-backed indexes. The default is the previous weekday, not the index-daily default. It needs database credentials only. Raw persistence is not proof that a valid clean row exists. An OK/PARTIAL ingest return must be followed by review of validation/completeness evidence.


```bash
python main.py index-daily-backfill --help
python main.py index-check --help
python main.py index-daily-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-check 19/10/2026 --indexes VNINDEX
```


## Stock technical features

All three routes are WRITE — feature calculation into `stock_features`, keyed by `(symbol,timeframe,time)`. No SSI credentials are needed. `1d` reads `stock_daily`; `15m` and `60m` aggregate existing clean 1m `stock_intraday` in memory with daily price context. Only closed buckets are persisted. `stock_intraday` continues to store only 1m. Unsupported feature persistence: `1m`, `5m`. Disabled source ingestion does not disable calculation over previously persisted intraday history.

`features` is the compatibility router: optional `--date`, `--mode incremental|full` (incremental default), optional symbols, default timeframes `15m 60m 1d`; it has no range or replace option. `features-daily` always selects 1d. `features-intraday` defaults to `15m 60m` and supports `--as-of` as Vietnam `HH:MM` or a timezone-aware timestamp. Do not combine as-of with a range. Explicit source-isolated routes require a target date, a complete range, or full mode.

Incremental uses per-stream watermarks and bounded warm-up (daily five years; intraday 250 observed sessions, not calendar days). A valid no-output incremental run may be an OK no-op. A range runs inclusive backfill. Full recomputes and upserts selected history without deletion and can consume substantial memory; it cannot combine with a date/range. Source corrections do not automatically invalidate old feature history.

**Potentially destructive WRITE — explicit rebuild:** replace and rebuild-clean are equivalent atomic scoped replacements. Require exactly one symbol, one persisted timeframe, and both range bounds; no wildcard/ALL, no `--date`. Compute and validate a non-empty replacement first, then call the existing service-role RPC to delete and rewrite exactly that scope. Confirm complete source/warm-up, inspect a source sample and retain before/after evidence before executing. These routes have no dry-run flag. Intraday replacement must explicitly choose one timeframe; the default two are rejected.


```bash
python main.py features --help
python main.py features-daily --help
python main.py features-intraday --help
python main.py features --date 19/10/2026 --symbols SSI HPG --timeframes 1d
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m --as-of 14:30
python main.py features-intraday --from 01/10/2026 --to 19/10/2026 --symbols SSI --timeframes 60m
python main.py features-daily --mode replace --symbols SSI --from 01/10/2026 --to 19/10/2026
python main.py features-intraday --mode rebuild-clean --symbols SSI --timeframes 15m --from 01/10/2026 --to 19/10/2026
```


## Foreign EOD features and rankings

Foreign V2 uses only same-symbol `stock_daily` rows ordered by trading date, with observed-row windows; it neither reads nor infers a calendar file. Missing foreign values remain missing. It writes only `stock_foreign_features_daily`, never repairs source rows. Historical corrections can affect following windows; review reported affected dates. See [Foreign EOD specification](FOREIGN_EOD_FEATURES.md).

Preview (`--symbol`, `--date`, optional `--show-source`/`--json`) and check (`--from`, `--to`, optional `--symbols`) are READ-ONLY — database read. Daily and backfill are WRITE — feature calculation unless `--dry-run`, which calculates/validates without persistence. Daily requires a date and accepts `--mode target|incremental` (target default); backfill requires both dates. Omitted symbols use active database scope. `--calendar-file` remains a deprecated ignored parser option, not a prerequisite.

`foreign-rank` and `foreign-symbol` are READ-ONLY — database RPC (`get_foreign_ranking`, `get_foreign_symbol_history`). Rank requires date/ranking; ranking is attention, accumulation, distribution or emerging. Window is 1/5/20 (default 5), sort value/ratio (default value); optional market, symbols, top (20), offset (0). History requires one symbol/date, lookback defaults 20. RPC/schema must exist separately; zero CLI exit does not certify nonempty/fresh results. Inspect row quality, coverage and source freshness before interpreting rankings.


```bash
python main.py foreign-features-preview --symbol SSI --date 19/10/2026 --show-source
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI HPG --dry-run
python main.py foreign-features-daily --date 19/10/2026 --symbols SSI --mode target
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI --dry-run
python main.py foreign-features-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-features-check --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking attention --window 1 --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --sort value --symbols SSI HPG --top 20
python main.py foreign-rank --date 19/10/2026 --ranking distribution --window 20 --sort ratio --top 20
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --sort value --top 20
python main.py foreign-symbol --symbol SSI --date 19/10/2026 --lookback 20
```


## Index features

The separate index feature domain reads `index_daily` and persists `index_features_daily` keyed by `(index_code,trading_date)`. It requires database access only; no SSI requests. Preview and check are READ-ONLY — database read. Daily and backfill are WRITE — feature calculation. Preview/daily require `--date`; backfill/check require `--from` and `--to` (no long date aliases here). Optional `--indexes` accepts space-separated master codes; omitted selects active master rows. Up to 250 prior clean sessions supply warm-up. No source OHLC or missing session is synthesized; insufficient windows retain nulls. Inspect raw-without-clean and missing-feature dates before rerunning an exact scope.


```bash
python main.py index-features-preview --date 19/10/2026 --indexes VNINDEX
python main.py index-features-daily --date 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-backfill --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX HNXINDEX
python main.py index-features-check --from 01/10/2026 --to 19/10/2026 --indexes VNINDEX
```


## Stock Screener V1 and V2

`stock-screener` requires `--date`, optionally symbols and `--version v1|v2` (v1 default). READ-ONLY — database read by default; reads active master symbols and exact-date 1d `stock_features`. It does not fetch or compute missing features. Missing input is not an invented passing result. `--apply` is WRITE — explicit apply to `stock_screener_results` using `(symbol,trading_date,screener_version)`.

`stock-screener-config` previews the local immutable V2 methodology without database access; defaults version v2, language vi (en also supported). With `--apply`, it reads/registers `screener_configs`; a conflicting hash is rejected. Register matching V2 config before V2 result writes. Existing screener migrations must already exist; do not apply them as part of reading this guide. Both methods are explainable research screens, not validated trading signals. See [Screener package](../src/research/screener/README.md) and [V2 methodology](../src/research/screener/methodologies/v2.md).


```bash
python main.py stock-screener --help
python main.py stock-screener-config --version v2 --language vi
python main.py stock-screener-config --version v2 --language en
python main.py stock-screener --date 19/10/2026 --symbols SSI HPG --version v1
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
python main.py stock-screener-config --version v2 --apply
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2 --apply
```


## Historical Analog lifecycle and research

The implemented tree is `profiles list|register|sync`, `history build`, `validate`, `approve`, `reject`, `query`, `inspect`, and `daily run`. There is no standalone report subcommand. Use the JSON from inspect/validate/query as reports. Dates here require DD/MM/YYYY. Profiles are immutable, identified by code/version/config hash; source V1 and V2 are available. Discover the source hash with registration dry-run before any DB registration.

Profile registration without apply is local, credential-free dry-run. Profile list reads `analog_profiles`. History build reads clean daily/features and builds snapshots/outcomes; without apply it is database-read calculation, with apply it writes `analog_snapshots` and `analog_outcomes`. Full/incremental use their existing persistence semantics; replace additionally requires `--confirm-replace` and can delete the exact profile/symbol/date scope. Never use a hash copied from an unrelated profile/version.

Inspect is READ-ONLY — database read plus research calculation, requiring an explicit distance threshold. Query and daily run are gated analysis workflows, READ-ONLY by default and WRITE — explicit apply when allowed. They can persist query/match evidence (`analog_queries`, `analog_query_matches`); they do not create trading signals. Approve/reject require a real validation-run ID, reviewer and reason; default dry-run, apply can write review/registry state (`analog_profile_reviews`, `analog_profiles`). The examples below intentionally use dry-runs. The illustrative review UUID must be replaced with an existing eligible run ID.

`--distance-threshold` remains required by the inspect parser, but the runtime ignores this compatibility threshold under its top-k matching contract; the example value does not alter matching.

**BLOCKED lifecycle point:** `validate --apply` is parsed but the current handler never forwards apply or persists its calibration/walk-forward result into `analog_validation_runs`. Review requires an existing validation row. Consequently the CLI alone does not establish a complete new validation/approval lifecycle; do not claim successful persisted validation from an exit 0. Calibration requires `--final-test-start`; optional threshold values are candidates, not production recommendations. Query can return `blocked` before constructing a DB client when the source profile is unapproved. No operation here bypasses approval gates.

Compare a symbol only with its own earlier history at the same EOD checkpoint. Outcomes must be observable by the query date; validation is chronological with a same-symbol/checkpoint baseline, never random splits or pooled symbols. `insufficient_sample` is a valid result, not permission to widen the universe. For the detailed evidence contract see [Historical Analog specification](phase1/HISTORICAL_ANALOG_SPEC.md).


```bash
python main.py analogs profiles list
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1
python main.py analogs profiles sync --profile TPLUS_ANALOG_CORE_EOD --version 1
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash d19417afed8718337c12aae7a668dd68e0f323dbb9c2316c92a5122759e9751b --symbols SSI --from 05/01/2026 --to 19/10/2026 --mode incremental
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 05/01/2026 --to 30/09/2026 --run-type calibration --final-test-start 01/10/2026 --thresholds 0.5 1.0
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/10/2026 --to 19/10/2026 --run-type validation
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/10/2026 --to 19/10/2026 --run-type final
python main.py analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 19/10/2026 --checkpoint EOD --distance-threshold 1.0
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 19/10/2026
python main.py analogs daily run --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --date 19/10/2026
python main.py analogs approve --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run 00000000-0000-0000-0000-000000000001 --reviewer operator --reason "Review existing final evidence"
python main.py analogs reject --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run 00000000-0000-0000-0000-000000000001 --reviewer operator --reason "Evidence incomplete"
```


## SSI v3 REST inspector

READ-ONLY — SSI API request; no Supabase access, even for master/intraday preview. `list` needs no credentials or network. `run` needs the SSI v3 key/secret, requests live data and maps supported datasets locally. Preview availability is not production-ingest readiness. See the [complete inspector runbook](../scripts/inspectors/ssi_rest/README.md) for native endpoints, compatibility aliases, paging, raw/clean mapping, dates, limits and errors.


```bash
python scripts/inspectors/ssi_rest/inspect.py --help
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 19/10/2026 --limit 5 --show-mapping
```


## Data quality and completeness tools

Phase 0 supports `1m`, `1d`, `15m`, `60m`; 1m needs no feature row. Schema checks use canonical stock_raw_intraday/stock_features and retain RPC security. Only ssi_v3 is remapped; legacy/missing/ambiguous evidence is UNKNOWN, verified mismatches FAIL. Intraday volume/value are exact integers, OHLC tolerance is 1e-6, aware timestamps match exact instants without rounding seconds. Closed observed buckets compare OHLCV/value using existing pure helpers; NULL/open/missing evidence is UNKNOWN, with no feature computation. Reconciliation exits 0 PASS/WARNING, 1 FAIL, 2 UNKNOWN; payload presence is informational. All diagnostics are read-only.

All active checks below are READ-ONLY — database read. `check_ingest.py` checks persisted stock daily/intraday coverage; it returns exit 0 for OK, 1 for PARTIAL/FAILED or query errors, and 2 for invalid/indeterminate results. JSON stdout preserves the original status; progress goes to stderr. Intraday missing data remains reportable independently of the isolated manual pilot. `check_supabase.py` has no CLI arguments or help parser: it performs core-table connectivity checks, not comprehensive schema certification. `check_ssi_ingest_schema.py` selects listed columns and prints index verification SQL; its legacy column expectations may be stale against contract 2.0 and need a separate code fix, not schema changes to satisfy the diagnostic.

`phase0_validate_schema.py` uses read-only PostgreSQL catalog queries; prefer the environment variable over putting a database URL in shell history. `phase0_reconcile_sample.py` checks one symbol/date/timeframe, optional exact timestamp and tolerance 1e-6. PASS/FAIL/UNKNOWN matter independently of process execution. See [checks](../scripts/checks/README.md).


```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
python scripts/checks/check_supabase.py
python scripts/checks/check_ssi_ingest_schema.py
python scripts/checks/phase0_validate_schema.py
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 15m
```


## Diagnostic, maintenance and debug scripts

The [script inventory](../scripts/README.md) covers every executable tool at its current location. **`scripts/previews/run_features.py` is WRITE — feature calculation**, despite its directory name. It invokes the engine, has no dry-run or date flag, and may process all selected history according to mode/watermarks. Prefer explicit main.py feature routes for a target date. Its naming/location is a separate code issue; it was not moved here.

`eod_dry_run.py`, `fetch_one_day.py`, capture scripts, streaming inspector and complete SSI smoke check are disabled stubs, not working debug pipelines. The legacy intraday-value SQL is a broad WRITE artifact without symbol/date scoping; it is not a routine operational CLI and must not be pasted into production. A separately reviewed scoped repair is required.


```bash
python scripts/previews/run_features.py --mode incremental --symbols SSI --timeframes 1d
```


## Temporarily disabled commands

The remaining disabled command groups below retain their parsers but fail before loading handlers or constructing SSI/DB clients. They return exit 1 and JSON status FAILED, error_type NOT_IMPLEMENTED. A rejected explicit source can instead return exit 2 in source preflight. Help still describes previous purposes; it is not evidence of availability.

| Command | Previous purpose | Required future adapter / dataset |
| --- | --- | --- |
| sync-master-data, init | Idempotent master sync | Verified v3 master adapters preserving operator status; master |
| intraday-ingest | Source 1m raw/clean ingestion | Verified v3 1m adapter, pagination, timestamps, units; stock_intraday |
| backfill | Combined daily/intraday plus checks | Same adapter; stock_intraday; no partial daily work |
| refill | Single-symbol source/check/features | Same adapter; stock_intraday; no partial daily/features work |
| streaming-ingest | Bounded streaming, optional write | Verified v3 protocol/auth/capture adapter; streaming |

Orderbook capture is likewise disabled pending a verified streaming adapter; do not invent a public REST depth endpoint. Historical raw/clean/master/feature/streaming rows remain stored and usable under their contracts. No fallback, deletion or historical repair occurs from calling a disabled command. Below are help commands only, not production success examples.


```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py stock-intraday-backfill --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```


## Exit codes, expected output and troubleshooting

CLI exit 0 includes supported OK and PARTIAL, plus domain statuses such as Analog blocked/dry_run/insufficient_sample. Exit 1 means FAILED, unavailable capability or a runtime exception. Exit 2 means argparse/ValueError validation or unsupported source. Most handlers test only `status == FAILED`; foreign RPC commands and index-preview return 0 after successful function return regardless of row completeness. Parsing success, API success, persistence success and completeness success are four different checks.

Illustrative output, not an observed execution:

```json
{"date":"19/10/2026","data_source":"ssi_v3","symbols":["SSI"],"daily_valid_count":1,"total_daily_rows":1,"error_count":0,"errors":[],"status":"OK"}
```

```json
{"status":"FAILED","error_type":"NOT_IMPLEMENTED","dataset":"stock_intraday","reason":"SSI v3 stock_intraday ingestion adapter is not implemented"}
```

| Symptom | Action |
| --- | --- |
| ImportError / missing create_client | Activate the installed venv and install requirements; the local supabase directory is not the Python SDK. |
| Invalid source / unrecognized option | Use only ssi_v3 where the parser supports a source option; auto selection means omit it. |
| Missing SSI credentials / 401 / 403 | Check the v3 key/secret and account entitlement locally; do not print tokens or use old consumer credentials. |
| NO_DATA / EMPTY_RESPONSE | Check exact symbol/date, publication delay and market session; do not fabricate rows or assume weekday means session. |
| MISMATCH / mapping failure | Inspect raw payload, record identity and mapping diagnostics; do not overwrite source evidence to force success. |
| Empty master scope | Inspect persisted symbols/index_master; disabled sync cannot populate it. |
| Raw exists but clean/features missing | Review validation failures and warm-up; run features separately only after source checks. |
| RPC/column/unique constraint error | Compare deployed schema with existing migrations; code checkout does not deploy database changes. |
| PARTIAL or exit 0 without output | Read warnings, counts, scope and per-day results; verify persisted rows/completeness independently. |
| Intraday incomplete | Compare timestamp/session rules for the selected symbol/date; never use one universal candle count. |
| Analog blocked / insufficient_sample | Inspect exact version/hash, prior observable history and approval evidence; do not pool symbols. |

REST inspector statuses PASS, EMPTY, FAILED refer to request/mapping inspection, not production database readiness.

## Database impact and operational safety

This change is documentation only: migration none, database impact none, required backfill none. Example WRITE operations would change data if deliberately run later; they were not executed for validation.

| Operation | Persistence target / impact |
| --- | --- |
| Stock source | stock_raw_daily source evidence; stock_daily validated clean rows |
| Index source | index_raw_daily evidence; index_daily clean rows |
| Stock features | stock_features upsert; scoped replace deletes/rewrites exact symbol/timeframe/date rows |
| Foreign features | stock_foreign_features_daily upsert |
| Index features | index_features_daily upsert |
| Screener apply | stock_screener_results; config apply registers screener_configs |
| Analog apply | Profile/history/query/review domain tables only, subject to gates; validation persistence is blocked as described above |
| Inspector/checks/dry-runs | No data writes; live reads may occur |

Raw and clean remain separate. Stock raw identity includes symbol/date/source/hash, stock clean symbol/date; index raw identity includes index/date/hash, index clean index/date. Confirm actual deployed constraints before write use. Rerun is not a rollback; old raw provenance is not permission to overwrite history broadly. Review explicit scope, counts, errors, nulls, source and timestamps after each operation. Never infer production completeness from offline tests.

Stock EOD workflow runs 16:30 Vietnam weekdays; Index EOD runs 08:30 Vietnam Tuesday–Saturday and resolves the previous day for scheduled publication timing. Manual CLI defaults differ; use an explicit date when reproducing a scheduled run. Intraday has no scheduled ingestion. Feature workflows are explicit. See [Data conventions](DATA_CONVENTIONS.md), [current state](CURRENT_STATE.md) and [restoration audit](CLI_DOCUMENTATION_AUDIT.md).

## Complete command inventory and arguments

Tables below reflect the current parser. `+` means one or more values, `*` zero or more at parsing (empty symbol scope still fails validation), `?` optional. Every command has `-h`, `--help`. Domain date/scope/output/failure semantics are explained above; see the exit-code section.

### `sync-master-data`

Previous source orchestration; currently unavailable.

**NOT_IMPLEMENTED** · Status: NOT_IMPLEMENTED.

Input: none / không gọi dịch vụ. Output/target: master.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `init`

Previous source orchestration; currently unavailable.

**NOT_IMPLEMENTED** · Status: NOT_IMPLEMENTED.

Input: none / không gọi dịch vụ. Output/target: master.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `daily`

Fetch stock daily; EOD aliases also check completeness.

**WRITE — raw/clean ingest** · Status: ACTIVE.

Input: SSI v3 securitiesSummary. Output/target: stock_raw_daily → stock_daily.

Credentials: SSI yes; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `date` | no | `—` | ? |
| `--data-source` | no | `—` | 1 |
| `--symbols` | no | `—` | + |

### `index-daily`

Fetch index daily source rows.

**WRITE — raw/clean ingest** · Status: ACTIVE.

Input: SSI v3 indexSummary. Output/target: index_raw_daily → index_daily.

Credentials: SSI yes; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `date` | no | `—` | ? |
| `--indexes` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `index-daily-backfill`

Compatible legacy alias: `index-backfill`.

Fetch index daily source rows.

**WRITE — raw/clean ingest** · Status: ACTIVE.

Input: SSI v3 indexSummary. Output/target: index_raw_daily → index_daily.

Credentials: SSI yes; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from`, `--from-date` | yes | `—` | 1 |
| `--to`, `--to-date` | yes | `—` | 1 |
| `--indexes` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `index-check`

Inspect index completeness.

**READ-ONLY — database read** · Status: ACTIVE.

Input: index_raw_daily + index_daily. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `date` | no | `—` | ? |
| `--indexes` | no | `—` | + |

### `index-preview`

Preview raw or normalized index source.

**READ-ONLY — SSI API request** · Status: ACTIVE.

Input: SSI v3 indexSummary. Output/target: terminal / JSON.

Credentials: SSI yes; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--date` | no | `—` | 1 |
| `--from` | no | `—` | 1 |
| `--to` | no | `—` | 1 |
| `--indexes` | yes | `—` | 1 |
| `--raw` | no | `false` | flag |
| `--json` | no | `false` | flag |

### `index-features-preview`

Inspect index feature calculation/coverage.

**READ-ONLY — database read** · Status: ACTIVE.

Input: index_daily + index_features_daily. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--date` | yes | `—` | 1 |
| `--indexes` | no | `—` | + |

### `index-features-daily`

Calculate index features.

**WRITE — feature calculation** · Status: ACTIVE.

Input: index_daily. Output/target: index_features_daily.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--date` | yes | `—` | 1 |
| `--indexes` | no | `—` | + |

### `index-features-backfill`

Calculate index features.

**WRITE — feature calculation** · Status: ACTIVE.

Input: index_daily. Output/target: index_features_daily.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from` | yes | `—` | 1 |
| `--to` | yes | `—` | 1 |
| `--indexes` | no | `—` | + |

### `index-features-check`

Inspect index feature calculation/coverage.

**READ-ONLY — database read** · Status: ACTIVE.

Input: index_daily + index_features_daily. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from` | yes | `—` | 1 |
| `--to` | yes | `—` | 1 |
| `--indexes` | no | `—` | + |

### `foreign-features-preview`

Inspect foreign feature calculations/quality.

**READ-ONLY — database read** · Status: ACTIVE.

Input: stock_daily + stock_foreign_features_daily. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--symbol` | yes | `—` | 1 |
| `--date` | yes | `—` | 1 |
| `--calendar-file` | no | `—` | 1 |
| `--json` | no | `false` | flag |
| `--show-source` | no | `false` | flag |

### `foreign-features-daily`

Calculate foreign features; dry-run suppresses writes.

**WRITE — feature calculation / --dry-run READ-ONLY** · Status: ACTIVE.

Input: stock_daily. Output/target: stock_foreign_features_daily.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--date` | yes | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--mode` | no | `"target"` | target, incremental |
| `--calendar-file` | no | `—` | 1 |
| `--dry-run` | no | `false` | flag |

### `foreign-features-backfill`

Calculate foreign features; dry-run suppresses writes.

**WRITE — feature calculation / --dry-run READ-ONLY** · Status: ACTIVE.

Input: stock_daily. Output/target: stock_foreign_features_daily.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from` | yes | `—` | 1 |
| `--to` | yes | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--calendar-file` | no | `—` | 1 |
| `--dry-run` | no | `false` | flag |

### `foreign-features-check`

Inspect foreign feature calculations/quality.

**READ-ONLY — database read** · Status: ACTIVE.

Input: stock_daily + stock_foreign_features_daily. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from` | yes | `—` | 1 |
| `--to` | yes | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--calendar-file` | no | `—` | 1 |

### `foreign-rank`

Rank attention/accumulation/distribution/emerging.

**READ-ONLY — database read** · Status: ACTIVE.

Input: get_foreign_ranking RPC. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--date` | yes | `—` | 1 |
| `--ranking` | yes | `—` | attention, accumulation, distribution, emerging |
| `--window` | no | `5` | 1, 5, 20 |
| `--sort` | no | `"value"` | value, ratio |
| `--market` | no | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--top` | no | `20` | 1 |
| `--offset` | no | `0` | 1 |

### `foreign-symbol`

Read symbol foreign history.

**READ-ONLY — database read** · Status: ACTIVE.

Input: get_foreign_symbol_history RPC. Output/target: JSON.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--symbol` | yes | `—` | 1 |
| `--date` | yes | `—` | 1 |
| `--lookback` | no | `20` | 1 |

### `intraday-ingest`

Previous source orchestration; currently unavailable.

**NOT_IMPLEMENTED** · Status: NOT_IMPLEMENTED.

Input: none / không gọi dịch vụ. Output/target: stock_intraday.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `date` | no | `—` | ? |
| `--symbols` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `stock-eod`

Fetch stock daily; EOD aliases also check completeness.

**WRITE — raw/clean ingest** · Status: ACTIVE.

Input: SSI v3 securitiesSummary. Output/target: stock_raw_daily → stock_daily.

Credentials: SSI yes; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `date` | no | `—` | ? |
| `--symbols` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `stock-daily`

Fetch stock daily; EOD aliases also check completeness.

**WRITE — raw/clean ingest** · Status: ACTIVE.

Input: SSI v3 securitiesSummary. Output/target: stock_raw_daily → stock_daily.

Credentials: SSI yes; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `date` | no | `—` | ? |
| `--symbols` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `stock-intraday`

**READ-ONLY by default / WRITE with `--write`** · Status: MANUAL_PILOT.

SSI v3 OHLC 1m → stock_raw_intraday → stock_intraday; no downstream work. SSI credentials required; Supabase optional for dry-run preflight and required for writes. See the pilot/runbook above.

| Argument | Required | Default | Values |
| --- | --- | --- | --- |
| `date` | yes (guard) | none | One DD/MM/YYYY or YYYY-MM-DD, not future |
| `--symbols` | yes (guard) | none | Exactly one symbol, both statuses active |
| `--data-source` | no | ssi_v3 | Only ssi_v3, dataset stock_intraday |
| `--write` | no | false | Authorize pilot persistence |
| `--dry-run` | no | read-only | Mutually exclusive with --write |

BLOCKED/PARTIAL/FAILED all exit 1; invalid scope exits 2. Dry-run creates no partition and actual inserts remain 0; planned counts use separate fields.

### `stock-daily-backfill`

Compatible legacy alias: `backfill-daily`.

Fetch daily history without completeness.

**WRITE — raw/clean ingest** · Status: ACTIVE.

Input: SSI v3 securitiesSummary. Output/target: stock_raw_daily → stock_daily.

Credentials: SSI yes; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from`, `--from-date` | yes | `—` | 1 |
| `--to`, `--to-date` | yes | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `stock-intraday-backfill`

Compatible alias `backfill-intraday`. **GUARDED_OPERATOR / DRY_RUN by default**, --write authorizes raw/clean inserts. Explicit symbols, at most 50 weekday pairs, SSI v3/1m only. No automatic features/completeness. Exit 0 OK, 1 any non-success range, 2 invalid input; see the runbook above.

| Argument | Required | Default | Values |
| --- | --- | --- | --- |
| `--from`, `--from-date` | yes | none | DD/MM/YYYY or YYYY-MM-DD, inclusive |
| `--to`, `--to-date` | yes | none | Inclusive, not future/reversed |
| `--symbols` | yes | none | Explicit normalized/deduplicated symbols; no ALL/wildcards/comma |
| `--data-source` | no | ssi_v3 | Only ssi_v3 |
| `--dry-run` | no | read-only | Mutually exclusive with --write |
| `--write` | no | false | Permit each pair's guarded pilot persistence |

### `backfill`

Previous source orchestration; currently unavailable.

**NOT_IMPLEMENTED** · Status: NOT_IMPLEMENTED.

Input: none / không gọi dịch vụ. Output/target: stock_intraday.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--from`, `--from-date` | yes | `—` | 1 |
| `--to`, `--to-date` | yes | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--data-source` | no | `—` | 1 |

### `refill`

Previous source orchestration; currently unavailable.

**NOT_IMPLEMENTED** · Status: NOT_IMPLEMENTED.

Input: none / không gọi dịch vụ. Output/target: stock_intraday.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--symbol` | yes | `—` | 1 |
| `--from`, `--from-date` | yes | `—` | 1 |
| `--to`, `--to-date` | yes | `—` | 1 |
| `--data-source` | no | `—` | 1 |

### `features`

Compute stock technical features independently.

**WRITE — feature calculation** · Status: ACTIVE.

Input: stock_daily / clean stock_intraday 1m. Output/target: stock_features.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--mode` | no | `"incremental"` | incremental, full |
| `--date` | no | `—` | 1 |
| `--symbols` | no | `—` | * |
| `--timeframes` | no | `["15m", "60m", "1d"]` | * |

### `features-daily`

Compute stock technical features independently.

**WRITE — feature calculation** · Status: ACTIVE.

Input: stock_daily / clean stock_intraday 1m. Output/target: stock_features.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--mode` | no | `"incremental"` | incremental, full, replace, rebuild-clean |
| `--date` | no | `—` | 1 |
| `--from`, `--from-date` | no | `—` | 1 |
| `--to`, `--to-date` | no | `—` | 1 |
| `--symbols` | no | `—` | * |

### `features-intraday`

Compute stock technical features independently.

**WRITE — feature calculation** · Status: ACTIVE.

Input: stock_daily / clean stock_intraday 1m. Output/target: stock_features.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--mode` | no | `"incremental"` | incremental, full, replace, rebuild-clean |
| `--date` | no | `—` | 1 |
| `--from`, `--from-date` | no | `—` | 1 |
| `--to`, `--to-date` | no | `—` | 1 |
| `--symbols` | no | `—` | * |
| `--timeframes` | no | `["15m", "60m"]` | * |
| `--as-of` | no | `—` | 1 |

### `stock-screener`

Evaluate active symbols using V1/V2; opt-in result writes.

**READ-ONLY / --apply WRITE** · Status: RESEARCH_ACTIVE.

Input: symbols + stock_features 1d. Output/target: JSON / stock_screener_results.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--date` | yes | `—` | 1 |
| `--symbols` | no | `—` | + |
| `--apply` | no | `false` | flag |
| `--version` | no | `"v1"` | v1, v2 |

### `stock-screener-config`

Inspect/register immutable V2 config.

**LOCAL / --apply WRITE** · Status: RESEARCH_ACTIVE.

Input: local V2 config + methodologies. Output/target: JSON / screener_configs.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--version` | no | `"v2"` | v2 |
| `--language` | no | `"vi"` | vi, en |
| `--apply` | no | `false` | flag |

### `streaming-ingest`

Previous source orchestration; currently unavailable.

**NOT_IMPLEMENTED** · Status: NOT_IMPLEMENTED.

Input: none / không gọi dịch vụ. Output/target: streaming.

Credentials: SSI no; Supabase no. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--symbols` | no | `[]` | * |
| `--indexes` | no | `[]` | * |
| `--channels` | yes | `—` | securities-status, quote, trade, foreign-room, index, realtime-bar |
| `--timeout` | no | `60` | 1 |
| `--max-messages-per-channel` | no | `1` | 1 |
| `--write` | no | `false` | flag |
| `--debug` | no | `false` | flag |

### `analogs`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `analogs profiles`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `analogs profiles list`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `analogs profiles register`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | no | `"TPLUS_ANALOG_CORE_EOD"` | 1 |
| `--version` | no | `1` | 1 |
| `--config-hash` | no | `—` | 1 |
| `--apply` | no | `false` | flag |

### `analogs history`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `analogs history build`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--config-hash` | yes | `—` | 1 |
| `--symbols` | yes | `—` | + |
| `--from` | yes | `—` | 1 |
| `--to` | yes | `—` | 1 |
| `--mode` | yes | `—` | full, incremental, replace |
| `--apply` | no | `false` | flag |
| `--confirm-replace` | no | `false` | flag |

### `analogs validate`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--symbols` | yes | `—` | + |
| `--from` | yes | `—` | 1 |
| `--to` | yes | `—` | 1 |
| `--run-type` | yes | `—` | calibration, validation, final |
| `--thresholds` | no | `—` | * |
| `--final-test-start` | no | `—` | 1 |
| `--apply` | no | `false` | flag |

### `analogs approve`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--validation-run` | yes | `—` | 1 |
| `--reviewer` | yes | `—` | 1 |
| `--reason` | yes | `—` | 1 |
| `--apply` | no | `false` | flag |

### `analogs reject`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--validation-run` | yes | `—` | 1 |
| `--reviewer` | yes | `—` | 1 |
| `--reason` | yes | `—` | 1 |
| `--apply` | no | `false` | flag |

### `analogs query`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--symbol` | yes | `—` | 1 |
| `--date` | yes | `—` | 1 |
| `--checkpoint` | no | `"EOD"` | EOD |
| `--apply` | no | `false` | flag |

### `analogs inspect`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--symbol` | yes | `—` | 1 |
| `--date` | yes | `—` | 1 |
| `--checkpoint` | no | `"EOD"` | EOD |
| `--distance-threshold` | yes | `—` | 1 |

### `analogs daily`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |

### `analogs daily run`

Same-symbol EOD research; explicit lifecycle.

**READ-ONLY / --apply WRITE (gated)** · Status: RESEARCH_ACTIVE.

Input: stock_daily + stock_features + analog_*. Output/target: JSON / analog_*.

Credentials: SSI no; Supabase yes. Local config/profile dry-runs and Analog gates have the exceptions described above.

| Argument / alias | Required | Default | Values / arity |
| --- | --- | --- | --- |
| `--profile` | yes | `—` | 1 |
| `--version` | yes | `—` | 1 |
| `--symbols` | yes | `—` | + |
| `--date` | yes | `—` | 1 |
| `--apply` | no | `false` | flag |

### WRITE profile registration — after reviewing the dry-run

This is WRITE — explicit apply to analog_profiles and needs database access; it is not a documentation-validation command.

```bash
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1 --apply
```

For a new local .env, copy the template without overwriting existing configuration:

```bash
cp -n .env.example .env
```

## Multi-page SSI v3 intraday preview (read-only)

The REST inspector stock-intraday/native intraday-ohlc routes now use the shared preview adapter and download successive pages from the requested start until explicit termination or failure/bound. `--limit` limits display only; `--full-json` includes every received raw page and clean candidate. `--max-pages` defaults to 100 (1–1000); hitting the bound, repeated pages, inconsistent totals or request failures return FAILED/exit 1 and retain received evidence. Other daily/index/catalog inspector routes keep their single-page behavior.

Owner-provided live SSI excerpts for 2026-10-20 verify `ohlc.tradingDate` in `YYYY/MM/DD HH:mm:ss`, source `ohlc.value`, and terminal `{"code":204,"msg":"No Content"}`. This exact source-local timestamp is explicitly interpreted in `Asia/Ho_Chi_Minh` and normalized to UTC; valid explicit-offset forms remain supported. The legacy `time` alias still requires an explicit timezone. Date-only/time-only and arbitrary naive formats remain rejected; no request-date fabrication or minute shifting.

Canonical v3 `value` is **SSI-reported intraday candle value**, parsed exactly as a nonnegative signed-BIGINT integer without float conversion. There is **no calculated estimate or fallback**. Absent/null/empty source value stays NULL with SOURCE_VALUE_MISSING; malformed/non-finite/fractional/negative/overflow value rejects the candidate. Zero stays zero. Source-value presence, numeric validity and preservation are reported separately from independently verified market-data semantics (still false).

The verified 204/No Content envelope terminates OHLC 1m paging only without conflicting payload/error markers and after metadata/count checks. Its original envelope is retained and termination is provider_no_content_204. Short nonempty pages never terminate by themselves; repeats, wrong totals, malformed/errors and page-limit truncation still fail. --limit controls display only; --full-json retains received raw pages, candidates and diagnostics.

The supplied day had 226 unique rows over 23 nonempty pages then page 24, descending order, 135 morning/90 afternoon/one 14:45 candle. These are owner-reported observations for that day, not a universal count or a formula rule. Only two real candle objects and the terminal envelope were supplied; offline replay verifies those 2/2 without reconstructing missing rows. Agent live rerun: NOT_RUN (no credentials). Bar-start/end, independent value/turnover semantics and market completeness remain unverified. Unattended ingestion/scheduling remains disabled; the inspector preview performs zero database reads/writes. The isolated manual pilot is described above.

See the [runbook and promotion checklist](STOCK_INTRADAY_PIPELINE.md) for field mappings, paging, validation/session/gap rules, source limitations and separate promotion steps.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```
