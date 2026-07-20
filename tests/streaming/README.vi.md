# Test streaming

Test streaming snapshot ingest và contract migration additive.

- `test_streaming_ingest_pipeline.py`: an toàn dry-run, giữ raw khi clean không hợp lệ và trạng thái timeout rỗng.
- `test_streaming_migration.py`: SQL additive/idempotent và chặn câu lệnh phá hủy.

```bash
python -m pytest -q tests/streaming
```
