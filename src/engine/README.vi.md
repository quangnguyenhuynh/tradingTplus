# Utility engine legacy

Package này hiện chỉ còn `data_quality.py`, một utility quality/recompute manual legacy. Phần tính feature deterministic thuộc [`src/features/`](../features/README.vi.md).

Các strategy signal legacy, entrypoint signal đã tắt và backtest MVP đã bị xóa trong Phase 0 vì phụ thuộc hợp đồng feature cũ. Hiện không có đường chạy signal hoặc backtest. Hai tầng này sẽ có hợp đồng mới trong phase thiết kế riêng sau khi data và feature được kiểm chứng.

Ingest không tự động tính feature, và feature không kích hoạt tầng research downstream nào.

```bash
python -m pytest -q tests/features
```
