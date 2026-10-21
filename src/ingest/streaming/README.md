# src/ingest/streaming

NOT_IMPLEMENTED: streaming/orderbook capture. Historical payload decoding and pure snapshot builders are offline utilities, not a verified current streaming protocol.

Existing tables, formulas and historical provenance are unchanged. No schema migration or data backfill is required.

Modules:

- `orderbook_snapshot.py`
- `payloads.py`
- `streaming_snapshot.py`

See the root README and docs/CURRENT_STATE.md for capability status and future adapter requirements.
