# Ingest tests

Tests for SSI daily/intraday normalization and ingest orchestration.

## Files

- `test_fetch_one_day.py`: daily/intraday mappers and services, UTC conversion, nullable fields, estimated value, invalid timestamps, compatibility imports, and daily/intraday separation.
- `test_intraday_value.py`: estimated intraday value calculation and NULL handling.
- `test_daily_ingest_payload_reuse.py`: one `DailyStockPrice` payload reused for raw, clean, and foreign records.
- `test_intraday_ingest_pipeline.py`: symbol scope, daily context, and partial status.
- `test_ingest_check.py`: completeness-query date ranges and counts.

```bash
python -m pytest -q tests/ingest
```
