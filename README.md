# Trading T+

Python data infrastructure and same-symbol historical research for Vietnamese stocks over T+3 to T+5 sessions. Phase 0 is `COMPLETE_WITH_NOTES`; research evidence and chronological validation take priority over trading automation.

| Capability | Status |
| --- | --- |
| SSI v3 Stock Daily / Index Daily | ACTIVE |
| SSI v3 Stock Intraday ingestion | NOT_IMPLEMENTED |
| SSI v3 Master Data synchronization | NOT_IMPLEMENTED |
| SSI v3 Streaming / Orderbook | NOT_IMPLEMENTED |
| Stock technical, foreign and index features | ACTIVE |
| Historical Analog / Screener V1/V2 | RESEARCH_ACTIVE |
| SSI v2 REST / legacy SignalR connection | RETIRED |

The thin `main.py` entrypoint calls `src.cli`. CLI parsing and source/capability preflight precede service access. Domain handlers call `src.ingest` services, which use the provider registry, `src.contracts`, `src.quality`, and existing raw/clean persistence. `src.providers.ssi` has no ingest or database dependency. Contracts contain no endpoint-specific request logic.

`src.features.stock`, `.foreign`, and `.index` run independently on persisted clean data. `src.research.screener` and `.analogs` preserve their formulas, configurations, profiles and research storage contracts. Intraday ingestion being unavailable does not prevent features from reading historical clean 1m candles.

## Setup and commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --help
python main.py stock-eod --help
python main.py index-daily --help
python main.py features-intraday --help
```

Daily ingest requires `SSI_API_KEY`, `SSI_API_SECRET`, `SUPABASE_URL` and a server-side Supabase key (`SUPABASE_SERVICE_KEY`, or the existing key configuration). Features/research need database configuration only. See `.env.example`; never commit credentials.

Active source commands: `daily`, `stock-eod` / `stock-daily`, `backfill-daily`, `index-daily`, `index-backfill`, `index-preview`, `index-check`. Only `ssi_v3` is accepted as a REST source. Invalid/retired sources return exit 2 before API/database access.

Unavailable commands preserve their parsers: `init`, `sync-master-data`, `intraday-ingest`, `stock-intraday`, `backfill-intraday`, `backfill`, `refill`, `streaming-ingest`. They return exit 1 and JSON `status=FAILED`, `error_type=NOT_IMPLEMENTED`, with no API/DB access. Combined backfill/refill never execute just the daily portion.

Features remain explicit: `features`, `features-daily`, `features-intraday`, foreign/index feature commands. Persisted stock feature timeframes remain `1d`, `15m`, `60m`; daily uses `stock_daily`, intraday aggregates historical clean `stock_intraday` 1m without writing aggregated candles back. Screener and Historical Analog remain research workflows.

No schema, RPC, conflict-key, migration or production-data changes are part of this restructuring. Historical raw/clean/master/streaming/features and source provenance remain untouched. No migration or backfill is required. Ingest never starts features or research automatically.

## References

- [Vietnamese guide](README.vi.md)
- [CLI usage](docs/CLI_USAGE.md)
- [Architecture](docs/ARCHITECTURE_DECISIONS.md)
- [Current state](docs/CURRENT_STATE.md)
- [Data conventions](docs/DATA_CONVENTIONS.md)
- [Foreign features](docs/FOREIGN_EOD_FEATURES.md)
- [Historical Analog contract](docs/phase1/HISTORICAL_ANALOG_SPEC.md)
- [File mapping](docs/RESTRUCTURE_MAPPING.json)
- [Pre-implementation audit](docs/RESTRUCTURE_AUDIT.md)

Root `schema.sql`, migration history and SQL contracts are preserved. Live production readiness/data completeness are not established by offline tests.
