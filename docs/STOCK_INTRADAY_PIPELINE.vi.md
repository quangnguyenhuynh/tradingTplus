# Pipeline Stock Intraday

`stock-intraday` là pipeline dữ liệu nguồn 1 phút tự động và độc lập. `.github/workflows/stock-intraday.yml` chạy lúc 10:00 UTC (17:00 Asia/Ho_Chi_Minh), thứ Hai-thứ Sáu, và có manual input `date`, `symbols` phân tách bằng dấu cách.

```bash
python main.py stock-intraday [DD/MM/YYYY] [--symbols SSI HPG]
```

## Scope và ngày

Scope tự động yêu cầu đồng thời `symbols.status='active'` và `symbols.intraday_status='active'`. Symbols explicit được strip, uppercase, loại trùng giữ thứ tự rồi giao với effective scope. Mã inactive/unknown nằm trong `ignored_symbols` và không được gửi tới SSI. Không resolve được mã nào sẽ trả `FAILED` rõ ràng.

Khi bỏ ngày, pipeline chọn ngày trong tuần gần nhất tính cả hôm nay theo giờ Việt Nam để action sau đóng cửa lấy ngày hiện tại. Đây không phải lịch nghỉ lễ; SSI rỗng vẫn được giữ rỗng và báo cáo.

## Stage và bảng

1. Resolve effective intraday scope.
2. Lấy SSI `IntradayOhlc` resolution 1.
3. Ghi payload nguồn vào `stock_raw_intraday`.
4. Validate và upsert candle canonical `timeframe='1m'` vào `stock_intraday`.
5. Kiểm tra completeness intraday-only: presence, duplicate, candle đầu/cuối, phiên sáng/chiều, missing interval và structural gap.
6. Tổng hợp status từ intraday.

SSI có thể bỏ phút không giao dịch; gap ngắn chỉ là quan sát/cảnh báo, không dùng một candle count universal. Không tạo candle giả.

Pipeline không ingest daily/index và không chạy feature, signal, backtest, Historical Analog hay automatic repair. Mapper có thể đọc daily context trong DB; thiếu context được báo. `backfill-intraday`, combined `backfill` và `refill` explicit vẫn là công cụ repair và có thể xử lý mã inactive được chỉ định.

Operator bật/tắt lần chạy intraday tự động tương lai bằng `symbols.intraday_status`; daily `status` cũng phải active. Thay đổi trạng thái không backfill market data.
