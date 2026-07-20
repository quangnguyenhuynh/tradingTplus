# Streaming tests

Tests for streaming snapshot ingest and additive migration contracts.

- `test_streaming_ingest_pipeline.py`: dry-run safety, raw retention for invalid clean records, and empty timeout status.
- `test_streaming_migration.py`: additive/idempotent SQL and protection against destructive statements.

```bash
python -m pytest -q tests/streaming
```
