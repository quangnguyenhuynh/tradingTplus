# Project overview

Trading T+ analyzes Vietnamese equities over T+3 to T+5 sessions. Data correctness, reproducible features and chronological same-symbol research precede signals, alerts and NAV decisions. No trading automation is introduced.

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

No schema, RPC, conflict-key, migration or production-data changes are part of this restructuring. Historical raw/clean/master/streaming/features and source provenance remain untouched. No migration or backfill is required. Ingest never starts features or research automatically.

See [CLI](CLI_USAGE.md), [conventions](DATA_CONVENTIONS.md), and [Historical Analog](phase1/HISTORICAL_ANALOG_SPEC.md).
