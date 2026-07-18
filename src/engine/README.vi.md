# Engine dữ liệu và research

Tính feature deterministic cùng code signal/backtest research downstream.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File chính

| File | Vai trò hiện tại |
| --- | --- |
| `feature_engine.py` | Đọc clean data, aggregate timeframe, tính và ghi `features`. |
| `feature_calculator.py` | Công thức indicator và feature. |
| `data_quality.py` | Kiểm tra chất lượng dữ liệu cho engine. |
| `signal_engine.py` | Signal engine rule-based dạng MVP/research. |
| `backtest_engine.py` | Backtest engine dạng MVP/research. |
| [`signal/`](signal/README.vi.md) | Các class rule signal dùng lại. |

## Hợp đồng feature

- Feature chạy tường minh và tách khỏi ingest.
- `1d` dùng `stock_daily`.
- `1m` dùng `stock_intraday`.
- `5m`, `15m`, `60m` được aggregate từ `1m` lúc tính feature.
- Kết quả nằm trong một bảng `features`, key `(symbol, timeframe, time)`.
- Incremental phải lấy đủ warm-up history.
- Full và incremental phải khớp trên phần dữ liệu giao nhau trong tolerance đã ghi rõ.
- Tính toán phải tách theo symbol, hiểu timeframe, chạy lại/backfill được và không look-ahead.

## Trạng thái signal và backtest

Signal/backtest là code downstream dạng research/MVP trong Phase 0. Chúng phải chạy riêng, không sửa dữ liệu nguồn và không được xem là bằng chứng sinh lợi đã kiểm chứng.

## Test

```bash
python -m pytest -q tests/test_feature_engine.py
python -m pytest -q tests/test_backtest_engine.py
```

Khi đổi công thức feature, phải ghi công thức cũ/mới, timeframe bị ảnh hưởng, dữ liệu lịch sử, nhu cầu backfill và test.
