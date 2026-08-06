# Utility engine legacy

Package này chứa `data_quality.py`, utility quality/recompute manual legacy.
Feature deterministic thuộc [`src/features/`](../features/README.vi.md).

Implementation fixed-rule strategy, signal và backtest nằm ở package riêng,
không phải đã bị xóa. Chúng đang đóng băng/đã bị thay thế và không phải đường
production Phase 1 được chấp nhận. Hướng mới nằm tại
[`docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md`](../../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).

Ingest không tự tính feature và feature không tự kích hoạt research downstream.

```bash
python -m pytest -q tests/features
```
