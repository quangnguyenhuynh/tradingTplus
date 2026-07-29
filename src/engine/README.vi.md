# Engine research downstream

Package này chứa code signal/backtest dạng research và một utility data-quality
legacy. Phần tính feature deterministic thuộc
[`src/features/`](../features/README.vi.md).

## File

| Đường dẫn | Vai trò hiện tại |
| --- | --- |
| `signal_engine.py` | Entrypoint signal legacy đã tắt; fail-fast vì rule cũ cần các cột feature đã xóa. |
| [`signal/`](signal/README.vi.md) | Các class rule legacy giữ lại để redesign sau; không nối vào production. |
| `backtest_engine.py` | Backtest MVP/research, phải chạy riêng. |
| `data_quality.py` | Utility quality/recompute manual legacy; không thuộc CLI ingest hoặc feature production. |

Hai compatibility shim `feature_engine.py` và `feature_calculator.py` đã bị xóa
và không được tạo lại. Import API feature từ `src.features`, hoặc dùng module
tách theo nguồn:

```python
from src.features.daily import run_daily_features_with_summary
from src.features.intraday import run_intraday_features_with_summary
```

Signal/backtest nằm downstream của feature đã kiểm chứng. Chúng phải chạy riêng,
không sửa dữ liệu nguồn và không được xem là bằng chứng sinh lợi đã xác nhận
trong Phase 0.

## Test

```bash
python -m pytest -q tests/features
python -m pytest -q tests/legacy/test_backtest_engine.py
```
