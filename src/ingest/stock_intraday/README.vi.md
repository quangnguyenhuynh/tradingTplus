# src/ingest/stock_intraday

[English](README.md)

## Các lệnh tạm tắt

Tám lệnh dưới giữ parser nhưng dừng trước khi nạp handler hoặc tạo client SSI/DB. Trả exit 1 và JSON status FAILED, error_type NOT_IMPLEMENTED. Source tường minh bị từ chối có thể trả exit 2 ở preflight trước đó. Help vẫn mô tả mục đích cũ, không chứng minh khả năng chạy.

| Lệnh | Mục đích trước đây | Adapter / dataset cần trong tương lai |
| --- | --- | --- |
| sync-master-data, init | Đồng bộ master idempotent | Adapter master v3 được xác minh, giữ status operator; master |
| intraday-ingest | Ingest raw/clean nguồn 1m | Adapter v3 1m, pagination, timestamp, đơn vị đã xác minh; stock_intraday |
| stock-intraday | Ingest 1m và completeness | Cùng adapter; stock_intraday |
| backfill-intraday | Lịch sử nguồn 1m | Cùng adapter; stock_intraday |
| backfill | Daily/intraday kèm check | Cùng adapter; stock_intraday; không chạy riêng phần daily |
| refill | Nguồn/check/feature một mã | Cùng adapter; stock_intraday; không chạy riêng daily/feature |
| streaming-ingest | Streaming giới hạn, ghi tùy chọn | Adapter protocol/auth/capture v3 đã xác minh; streaming |

Chụp orderbook cũng tắt đến khi có adapter streaming được xác minh; không tự tạo endpoint REST depth công khai. Raw/clean/master/feature/streaming lịch sử vẫn còn và dùng được theo contract. Gọi lệnh đang tắt không fallback, xóa hay sửa lịch sử. Dưới đây chỉ là help, không phải ví dụ chạy production thành công.

```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py backfill-intraday --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```
## Feature kỹ thuật cổ phiếu

Cả ba route đều WRITE — feature calculation vào `stock_features`, khóa `(symbol,timeframe,time)`. Không cần credential SSI. `1d` đọc `stock_daily`; `15m`, `60m` aggregate clean 1m `stock_intraday` trong bộ nhớ cùng ngữ cảnh giá daily. Chỉ persist bucket đã đóng. `stock_intraday` vẫn chỉ lưu 1m. Không hỗ trợ persist feature `1m`, `5m`. Tắt ingest nguồn không ngăn tính feature trên lịch sử intraday đã có.

`features` là router tương thích: tùy chọn `--date`, `--mode incremental|full` (mặc định incremental), mã tùy chọn, timeframe mặc định `15m 60m 1d`; không có range/replace. `features-daily` luôn chọn 1d. `features-intraday` mặc định `15m 60m`, hỗ trợ `--as-of` dạng `HH:MM` giờ Việt Nam hoặc timestamp có timezone. Không ghép as-of với khoảng ngày. Hai route tách nguồn bắt buộc ngày đích, cặp khoảng ngày hoặc full mode.

Incremental dùng watermark riêng mỗi stream và warm-up giới hạn (daily năm năm; intraday 250 phiên quan sát, không phải ngày lịch). Không có đầu ra mới có thể là OK không làm gì. Khoảng ngày chạy backfill bao gồm hai đầu. Full tính lại/upsert lịch sử đã chọn, không xóa; có thể tốn nhiều RAM, không ghép ngày/range. Sửa dữ liệu nguồn không tự vô hiệu feature cũ.

**WRITE — explicit rebuild có thể phá hủy dữ liệu:** replace và rebuild-clean cùng thay thế atomic một phạm vi. Bắt buộc đúng một mã, một timeframe được persist và hai đầu khoảng; không wildcard/ALL, không `--date`. Tính/validate bộ thay thế không rỗng trước, sau đó RPC service-role hiện có xóa và ghi lại đúng phạm vi. Xác nhận nguồn/warm-up đủ, đối soát mẫu, lưu bằng chứng trước/sau trước khi chạy. Không có cờ dry-run. Replace intraday phải chỉ định đúng một timeframe; mặc định hai timeframe bị từ chối.

```bash
python main.py features --help
python main.py features-daily --help
python main.py features-intraday --help
python main.py features --date 19/10/2026 --symbols SSI HPG --timeframes 1d
python main.py features-daily --date 19/10/2026 --symbols SSI
python main.py features-daily --from 01/10/2026 --to 19/10/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-intraday --date 19/10/2026 --symbols SSI --timeframes 15m 60m --as-of 14:30
python main.py features-intraday --from 01/10/2026 --to 19/10/2026 --symbols SSI --timeframes 60m
python main.py features-daily --mode replace --symbols SSI --from 01/10/2026 --to 19/10/2026
python main.py features-intraday --mode rebuild-clean --symbols SSI --timeframes 15m --from 01/10/2026 --to 19/10/2026
```

[CLI](../../../docs/CLI_USAGE.vi.md)
