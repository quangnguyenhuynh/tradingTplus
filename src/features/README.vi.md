# Package feature

`common.py` chứa phép toán thuần dùng chung, so sánh nullable, hợp đồng 35 cột và primitive serialize. `daily.py` công khai tính/chạy daily; `intraday.py` công khai chuẩn hóa 1m, aggregate observed-only, lọc bucket đã đóng và chạy intraday; `runner.py` quản lý phân trang hữu hạn, summary theo mã/lỗi và mixed orchestrator đã deprecated. Hai module `src.engine.feature_*` cũ chỉ là shim import tương thích.

## Nguồn và công thức

Luồng daily chỉ đọc `stock_daily`, ghi `features(timeframe='1d')`. Return daily là `close/open-1` và dùng close daily trước đó đã xác minh; MA/high/low daily vẫn rolling theo bar. Luồng intraday đọc `stock_intraday(timeframe='1m')`, chỉ được đọc `stock_daily` làm context `open_price` chính thức cùng ngày và `close_price` trước đó. 5m/15m/60m được aggregate trong bộ nhớ; timestamp là bucket start UTC timezone-aware, diễn giải theo `Asia/Ho_Chi_Minh`, không dùng audit timestamp.

EMA dùng pandas EWM `adjust=False` (span 9/20/50); RSI14 theo Wilder EWM (`alpha=1/14`, `adjust=False`); MACD là EMA12 trừ EMA26 với signal EMA9. EMA/RSI/MACD và high/low20 trước đó của intraday liên tục qua các ngày quan sát. VWAP reset mỗi ngày. `volume_ma20`/`value_ma20` intraday so bucket cùng phiên/giờ địa phương của 20 ngày quan sát trước, loại bucket hiện tại. Không tạo bucket thiếu. Flag chỉ true/false khi đủ hai input, nếu không ghi NULL.

`return_from_open` intraday dùng `stock_daily.open_price`; context thiếu/không hợp lệ giữ NULL. Previous close cũng từ `stock_daily`. Value intraday vẫn là ước tính `round(close * volume)`, nên VWAP là xấp xỉ, không phải VWAP turnover chính xác từ sở.

## Thực thi

Full và incremental dùng toàn bộ history trước đó sẵn có trong Phase 0 để EWM khớp trên phần giao (tolerance sau serialize: 1e-6). Read có phân trang và dừng khi hết nguồn; log có range, số bar aggregate, ngày quan sát và mức đủ warm-up. Incremental chỉ ghi target date. Production không ghi bucket còn mở; partial aggregate quan sát được chỉ có thể tồn tại trong memory. Bucket ngắn cuối phiên đóng tại biên phiên. Ngày lịch sử dùng biên phiên hoàn tất; ngày hiện tại dùng `now` Việt Nam hoặc `--as-of` an toàn (`HH:MM` trên target date hoặc timestamp có timezone).

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI HPG
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m
python main.py features-intraday --date 10/07/2026 --as-of 14:30 --symbols SSI
```

`features` là mixed router tương thích đã deprecated; `intraday` vẫn là alias incremental intraday. Feature command không gọi SSI/ingest/signal/backtest/alert. Mọi luồng chỉ ghi `features`, key `(symbol,timeframe,time)`.

Migration `20260729_drop_legacy_feature_columns.sql` xóa tám cột legacy không còn dùng và phải apply thủ công sau review. Raw/clean không đổi. Sau deploy cần full backfill canonical daily/intraday thủ công. Chỉ audit read-only các row cũ có thể từng ghi khi bucket mở; cleanup phải được duyệt và scope riêng.

Giới hạn: holiday/halt được suy từ dữ liệu quan sát thay vì calendar sở tích hợp; biên phiên là giả định cấu hình; nguồn thiếu giữ NULL; value xấp xỉ giới hạn độ chính xác VWAP; feature run là DB write nên không dùng làm production smoke test.
