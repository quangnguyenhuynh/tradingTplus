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

### Gap intraday, return và indicator

- Aggregate feature chỉ dùng candle 1m quan sát được trong `stock_intraday`. Bucket 5m/15m/60m có ít nhất một candle thì được tạo; bucket hoàn toàn trống không bị tạo giả. OHLC dùng first/max/min/last, volume/value chỉ sum candle quan sát được và không vượt ngày giao dịch Việt Nam hoặc giờ nghỉ trưa.
- `return_1m`, `return_5m`, `return_15m` là wall-clock/time-aware. Tại thời điểm row `t`, reference là candle gần nhất tại hoặc trước `t - horizon`, trong cùng ngày giao dịch Việt Nam và cùng phiên sáng/chiều. Tolerance backward là một phút cho horizon 1m và hai phút cho horizon 5m/15m. Reference thiếu hoặc stale cho kết quả null; không dùng candle tương lai, row overnight, forward-fill vô hạn hay return bằng zero.
- Contract cột giữ nguyên: 1m có cả ba return; 5m có 5m/15m; 15m có 15m; 60m không áp dụng; return 1d vẫn null.
- EMA9/20/50, RSI14, MACD, MA20 volume/value và high/low 20 bars vẫn **bar-based**. Ví dụ EMA20 trên 1m là EMA của 20 candle 1m quan sát được; nếu có phút không giao dịch, 20 candle có thể trải dài hơn 20 phút đồng hồ. Quy tắc này chủ ý khác với return time-aware.
- VWAP intraday vẫn là cumulative value của candle quan sát được chia cumulative volume quan sát được. Intraday value là ước tính chuẩn hóa `round(close * volume)`, không phải turnover SSI/exchange chính xác; không tạo volume/value cho phút trống.

Feature intraday lịch sử từng tính bằng `pct_change(n)` theo row cần backfill riêng tầng feature sau thay đổi này. Raw và clean không cần ingest lại.

## Trạng thái signal và backtest

Signal/backtest là code downstream dạng research/MVP trong Phase 0. Chúng phải chạy riêng, không sửa dữ liệu nguồn và không được xem là bằng chứng sinh lợi đã kiểm chứng.
Backtest MVP intraday chỉ chọn feature row tại hoặc trước signal time và từ chối entry cũ hơn giới hạn staleness mặc định hai phút; không bao giờ chọn row tương lai gần nhất.

## Test

```bash
python -m pytest -q tests/features/test_feature_engine.py
python -m pytest -q tests/legacy/test_backtest_engine.py
```

Khi đổi công thức feature, phải ghi công thức cũ/mới, timeframe bị ảnh hưởng, dữ liệu lịch sử, nhu cầu backfill và test.
