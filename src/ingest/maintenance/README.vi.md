# src/ingest/maintenance

Tên CLI canonical và alias tương thích (không có lịch bỏ alias): `stock-daily-backfill` → `backfill-daily`; `stock-intraday-backfill` → `backfill-intraday`. Chỉ tên CLI thay đổi; runner, tham số, flow JSON và exit code giữ nguyên. Stock Daily/Index Daily backfill ACTIVE / WRITE; Stock Intraday backfill DISABLED / NOT_IMPLEMENTED, tách biệt manual pilot.

[English](README.md)

## Backfill lịch sử Stock Daily

WRITE — raw/clean ingest: `stock-daily-backfill` bắt buộc `--from`, `--to`; alias là `--from-date`, `--to-date`. Mã tùy chọn áp dụng cho từng ngày; bỏ mã dùng master active trong mỗi lần ingest. Có thể chỉ định `--data-source ssi_v3`; bỏ tùy chọn chọn adapter v3 ready, không truyền chuỗi `auto`.

Runner bỏ cuối tuần, từ chối khoảng đảo/tương lai, ghi trạng thái OK/PARTIAL/FAILED từng ngày và tiếp tục khi có lỗi. Khoảng chỉ có cuối tuần là OK không làm gì. Không chạy completeness: đọc summary từng ngày và kiểm tra chỉ đọc với phạm vi riêng. Chạy lại có thể cập nhật clean và giữ bằng chứng raw. Không tính feature hay gọi combined backfill đang tắt.

```bash
python main.py stock-daily-backfill --help
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```
## Các lệnh tạm tắt

Các nhóm lệnh dưới giữ parser nhưng dừng trước khi nạp handler hoặc tạo client SSI/DB. Trả exit 1 và JSON status FAILED, error_type NOT_IMPLEMENTED. Source tường minh bị từ chối có thể trả exit 2 ở preflight trước đó. Help vẫn mô tả mục đích cũ, không chứng minh khả năng chạy.

| Lệnh | Mục đích trước đây | Adapter / dataset cần trong tương lai |
| --- | --- | --- |
| sync-master-data, init | Đồng bộ master idempotent | Adapter master v3 được xác minh, giữ status operator; master |
| intraday-ingest | Ingest raw/clean nguồn 1m | Adapter v3 1m, pagination, timestamp, đơn vị đã xác minh; stock_intraday |
| stock-intraday-backfill | Lịch sử nguồn 1m | Cùng adapter; stock_intraday |
| backfill | Daily/intraday kèm check | Cùng adapter; stock_intraday; không chạy riêng phần daily |
| refill | Nguồn/check/feature một mã | Cùng adapter; stock_intraday; không chạy riêng daily/feature |
| streaming-ingest | Streaming giới hạn, ghi tùy chọn | Adapter protocol/auth/capture v3 đã xác minh; streaming |

Chụp orderbook cũng tắt đến khi có adapter streaming được xác minh; không tự tạo endpoint REST depth công khai. Raw/clean/master/feature/streaming lịch sử vẫn còn và dùng được theo contract. Gọi lệnh đang tắt không fallback, xóa hay sửa lịch sử. Dưới đây chỉ là help, không phải ví dụ chạy production thành công.

```bash
python main.py init --help
python main.py sync-master-data --help
python main.py intraday-ingest --help
python main.py stock-intraday --help
python main.py stock-intraday-backfill --help
python main.py backfill --help
python main.py refill --help
python main.py streaming-ingest --help
```

[CLI](../../../docs/CLI_USAGE.vi.md)
