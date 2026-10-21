# src — SSI v3

The thin `main.py` entrypoint calls `src.cli`. CLI parsing and source/capability preflight precede service access. Domain handlers call `src.ingest` services, which use the provider registry, `src.contracts`, `src.quality`, and existing raw/clean persistence. `src.providers.ssi` has no ingest or database dependency. Contracts contain no endpoint-specific request logic.

`src.features.stock`, `.foreign`, and `.index` run independently on persisted clean data. `src.research.screener` and `.analogs` preserve their formulas, configurations, profiles and research storage contracts. Intraday ingestion being unavailable does not prevent features from reading historical clean 1m candles.

| Capability | Status |
| --- | --- |
| SSI v3 Stock Daily / Index Daily | ACTIVE |
| SSI v3 Stock Intraday ingestion | NOT_IMPLEMENTED |
| SSI v3 Master Data synchronization | NOT_IMPLEMENTED |
| SSI v3 Streaming / Orderbook | NOT_IMPLEMENTED |
| Stock technical, foreign and index features | ACTIVE |
| Historical Analog / Screener V1/V2 | RESEARCH_ACTIVE |
| SSI v2 REST / legacy SignalR connection | RETIRED |

No schema, RPC, conflict-key, migration or production-data changes are part of this restructuring. Historical raw/clean/master/streaming/features and source provenance remain untouched. No migration or backfill is required. Ingest never starts features or research automatically.
