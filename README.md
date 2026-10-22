# TradingTPlus — SSI v3

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
python main.py backfill-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
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
