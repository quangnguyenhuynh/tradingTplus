# src/ingest/workflows

[English](README.md)

## Ingest Stock Daily

`daily`: WRITE — raw/clean ingest. Đọc SSI v3 `securitiesSummary`, giữ payload/hash nguồn trong `stock_raw_daily`, validate rồi lưu `stock_daily` chuẩn. Không chạy completeness hay tính toán tầng sau. Bỏ ngày: chọn ngày trong tuần gần nhất trước hôm nay tại Việt Nam. Mã tường minh được dùng trực tiếp; bỏ mã: lấy master active đã lưu.

`stock-eod` và alias chính xác `stock-daily`: WRITE — raw/clean ingest kèm completeness chỉ cho daily. Mã tường minh được giao với master active, báo các mã không biết/inactive bị bỏ. Không có mã active trả FAILED. Ngày mặc định là ngày trong tuần gần nhất tính cả hôm nay tại Việt Nam, khác `daily`. Completeness đối chiếu thời điểm lần chạy và source kỳ vọng. Không ingest index/intraday, không ghi dataset foreign-trading riêng, không tự chạy feature. Trường đếm/summary intraday cũ không có nghĩa là đã ingest intraday.

Ngày ghi nguồn tường minh ở cuối tuần/tương lai bị từ chối. Ngày nghỉ trả rỗng được báo, không tạo hàng giả. Cần cả credential SSI và Supabase.

```bash
python main.py daily --help
python main.py stock-eod --help
python main.py stock-daily --help
python main.py daily 19/10/2026 --symbols SSI
python main.py daily 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py daily --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-daily 19/10/2026 --symbols SSI HPG
```
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

[CLI](../../../docs/CLI_USAGE.vi.md)
