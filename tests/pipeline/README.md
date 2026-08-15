# Pipeline tests

Tests for end-of-day orchestration and read-only dry-run behavior.

They verify that EOD runs ingest and completeness checks without automatically running features, and that dry-run inspection does not instantiate or write through the database client.
`test_refill_pipeline.py` additionally verifies exact single-symbol scope, source-before-feature ordering, status gating, independent feature error reporting, weekend no-op behavior, and the absence of delete/replace or downstream calls.

```bash
python -m pytest -q tests/pipeline
```
