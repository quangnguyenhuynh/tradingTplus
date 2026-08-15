# Test pipeline

Test điều phối cuối ngày và hành vi dry-run chỉ đọc.

Các test xác nhận EOD chạy ingest và completeness nhưng không tự chạy feature; dry-run không khởi tạo hoặc ghi qua database client.
`test_refill_pipeline.py` còn xác nhận scope đúng một mã, thứ tự source trước feature, status gating, báo lỗi độc lập giữa hai nhánh feature, no-op cuối tuần và không có lệnh delete/replace hoặc downstream.

```bash
python -m pytest -q tests/pipeline
```
