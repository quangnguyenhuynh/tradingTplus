# Pipeline tests

Tests for end-of-day orchestration and read-only dry-run behavior.

They verify that EOD runs ingest and completeness checks without automatically running features, and that dry-run inspection does not instantiate or write through the database client.

```bash
python -m pytest -q tests/pipeline
```
