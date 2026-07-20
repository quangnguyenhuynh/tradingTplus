# Test pipeline

Test điều phối cuối ngày và hành vi dry-run chỉ đọc.

Các test xác nhận EOD chạy ingest và completeness nhưng không tự chạy feature; dry-run không khởi tạo hoặc ghi qua database client.

```bash
python -m pytest -q tests/pipeline
```
