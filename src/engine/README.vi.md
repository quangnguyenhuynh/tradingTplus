# Utility engine legacy

Package này chứa `data_quality.py`, utility quality/recompute manual legacy.
Feature deterministic thuộc [`src/features/`](../features/README.vi.md).

Implementation strategy, signal và backtest kiểu rule cũ đã bị xóa. Hợp đồng Phase 1 active nằm tại
[`docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md`](../../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).

Ingest không tự tính feature và feature không tự kích hoạt research downstream.

```bash
python -m pytest -q tests/features
```
