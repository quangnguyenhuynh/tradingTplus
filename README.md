# TradingTPlus — SSI v3

## Guarded operator intraday backfill

`stock-intraday-backfill` (compatible alias `backfill-intraday`) now runs the existing guarded manual pilot sequentially for an explicit inclusive range and explicit symbols. Default is **DRY_RUN**; only `--write` persists. `--dry-run`/`--write` are mutually exclusive. Dates accept DD/MM/YYYY or YYYY-MM-DD and keep --from-date/--to-date aliases. No ALL/wildcards/comma scopes, implicit universe, future/inverted ranges or force overwrite. Normalize/deduplicate symbols in input order; process dates ascending and symbols in that order. Reject more than **50 symbol/weekday pairs** before services. Weekends skip without calls; a weekend-only range is an OK no-op.

```bash
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --dry-run
# Owner only, after reviewing the dry-run/preflight:
python main.py stock-intraday-backfill --from 19/10/2026 --to 21/10/2026 --symbols SSI HPG --data-source ssi_v3 --write
```

Each pair reuses `run_manual_intraday()` eligibility (both persisted statuses active), SSI v3 whole-day pagination/mapping/value validation, exact Vietnam-day UTC conflict preflight, raw-first insert-only persistence and scoped readback. No SSI v2, timestamp repair, value estimate, batch filtering or conflicting overwrite. Preserve raw source JSON/hash and exact BIGINT `ohlc.value`; completeness stays UNVERIFIED, with no 226-bar requirement. A valid empty source is NO_SOURCE_DATA, not a verified holiday or success. Unsupported historical dates and invalid batches remain explicit failures. Dry-run performs zero mutations/partition RPCs and reports actual inserts=0 with separate planned counts; absent DB preflight is BLOCKED, never write-ready.

Ordinary pair conflicts/source validation errors continue safely; systemic configuration/auth/exhausted shared-dependency errors halt with completed and unprocessed scopes reported. No automatic retry of ambiguous DB writes. Pair PARTIAL retains raw commits, acknowledged counts and recovery; inspect exact scope read-only, resolve the cause, then explicitly rerun. Identical rows skip and missing clean can be completed under the existing guards; no cleanup/delete or cross-table atomicity claim. Range OK requires every planned pair verified (or no work); mixed verified success/failure is PARTIAL; no verified success with failures is FAILED, even when a pair committed partial raw data. Per-pair PARTIAL/insert counts remain visible in that FAILED range. CLI exits 0 only for OK, 1 for any non-success/unverified range, 2 for invalid scope/source/arguments. Other CLI exits are unchanged.

Range JSON retains `flow=backfill-intraday`, reports planned/processed/OK/blocked/partial/failed/no-source pairs, totals, planned inserts, halted/unprocessed scopes and full pilot summaries in per_symbol_date. Only summaries survive each pair; raw/clean working batches are released. Registry remains preview with no generic intraday production factory. Single-symbol/day stock-intraday is unchanged; intraday-ingest, combined backfill, refill, master and streaming stay disabled. No automatic feature/completeness/signal/backtest/alert stage. Workflow stock-intraday remains disabled and unscheduled. No migration or development backfill; Codex performs no live writes. See [runbook](docs/backfill/README.md) for operator recovery and post-write read-only checks.

Canonical CLI names and compatible legacy aliases (no removal date): `stock-daily-backfill` → `backfill-daily`. Compatible CLI spellings remain; daily/index behavior is unchanged. Intraday uses the guarded operator range contract. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is guarded operator-only, DRY_RUN by default, with explicit --write and at most 50 weekday pairs; unattended routes remain disabled.

[Tiếng Việt](README.vi.md)

Trading T+ researches Vietnamese stocks over roughly T+3–T+5 trading sessions. Phase 0 is COMPLETE_WITH_NOTES; Phase 1 is same-symbol, same-checkpoint Historical Analog EOD research. Research output does not automatically create signals, alerts or NAV allocation.

## Architecture

`main.py → src/cli → src/ingest` orchestrates ingestion. `src/providers/ssi` selects v3 clients/adapters; `src/contracts` maps/validates contracts and `src/quality` checks quality. `src/database` keeps raw/clean persistence separate. `src/features/{stock,foreign,index}` independently reads clean data; `src/research/{screener,analogs}` is downstream research. Ingestion never starts features or research automatically.

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

## Current capabilities

Verified against `dev` commit `b5cb3276` (PR #178). Run from the repository root. Examples use illustrative dates and symbols; check source availability and choose the exact intended scope before executing. Syntax was checked offline, not against live SSI or Supabase.

SSI v3 Stock Daily (`securitiesSummary`) and Index Daily (`indexSummary`) ingestion are ACTIVE. Stock, foreign and index features are ACTIVE on persisted clean data. Screener and Historical Analog are RESEARCH_ACTIVE. Stock intraday has an isolated manual single-symbol/day pilot (read-only unless `--write`); unattended intraday, master synchronization, streaming and orderbook capture remain NOT_IMPLEMENTED. See [manual runbook](docs/STOCK_INTRADAY_PIPELINE.md). The retired source has no fallback.

READ-ONLY — database read means no writes but still requires database access. READ-ONLY — SSI API request can make live requests without using Supabase. WRITE labels identify persistence, including explicit apply and scoped replacement. UNSUPPORTED means an input or operation is rejected, not an empty successful result.

## Quick start and common operations

Start with read-only SSI preview. Source ingestion requires existing master data: master sync is disabled, so an empty installation cannot bootstrap itself with `init`. After validating the ingest summary, calculate features explicitly. Each command below is independent; stop and inspect its result before continuing.

The preview is READ-ONLY — SSI API request. Stock EOD is WRITE — raw/clean ingest. Daily features are WRITE — feature calculation. Screener defaults to READ-ONLY — database read. Do not execute all writes merely to test documentation.
```bash
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 19/10/2026 --show-mapping
python main.py stock-eod 19/10/2026 --symbols SSI --data-source ssi_v3
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py stock-screener --date 19/10/2026 --symbols SSI --version v2
```

```bash
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py index-preview --date 19/10/2026 --indexes VNINDEX --json
python main.py foreign-rank --date 19/10/2026 --ranking accumulation --window 5 --symbols SSI --top 20
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1
```

Write examples can update raw/clean/features if executed. Choose the exact scope and inspect each summary before the next stage. Exit 0 can mean PARTIAL/blocked; it does not certify completeness. Existing master data is required because init/sync is disabled. Replace/rebuild-clean can delete/rewrite exact feature scope; read the safety instructions first.

## Detailed documentation

- [CLI](docs/CLI_USAGE.md)
- [Scripts](scripts/README.md)
- [SSI REST inspector](scripts/inspectors/ssi_rest/README.md)
- [Architecture / domain map](src/README.md)
- [Stock features](src/features/stock/README.md)
- [Foreign EOD](docs/FOREIGN_EOD_FEATURES.md)
- [Index features](src/features/index/README.md)
- [Historical Analog](src/research/analogs/README.md)
- [Screener](src/research/screener/README.md)
- [Data conventions](docs/DATA_CONVENTIONS.md)
- [Current state](docs/CURRENT_STATE.md)

## Offline checks

```bash
python main.py --help
python -m compileall main.py src scripts tests
python -m pytest -q tests/cli tests/inspectors
```

This documentation task changes no schema/data, requires no migration/backfill, and does not execute write examples for validation.

For a new local .env, copy the template without overwriting existing configuration:

```bash
cp -n .env.example .env
```
