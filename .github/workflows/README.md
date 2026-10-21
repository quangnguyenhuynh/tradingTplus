# .github/workflows — SSI v3

Stock EOD keeps 09:30 UTC Mon–Fri; index EOD keeps 01:30 UTC Tue–Sat. Tests and explicit feature execution remain unchanged. Stock intraday has workflow_dispatch only, emits NOT_IMPLEMENTED and exits 1 without credentials or network/DB access. No scheduled master/streaming jobs exist.

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
