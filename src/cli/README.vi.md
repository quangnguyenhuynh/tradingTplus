# src/cli — parser và điều phối

[English](README.md)

`parser.py` định nghĩa tham số; `__init__.py` parse trước, kiểm tra source/capability trước khi nạp handler domain. Help không gọi dịch vụ. `stock`, `index`, `features`, `foreign`, `screener`, `analogs`, `maintenance`, `streaming` chỉ điều phối, không trộn công thức hay tự bật nguồn tắt. `common.py` in summary và map FAILED thành exit 1; ValueError thành 2, PARTIAL có thể 0.

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
python main.py --help
python main.py features-daily --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py foreign-rank --date 19/10/2026 --ranking emerging --window 5 --top 20
```

[Danh mục tất cả lệnh, tham số, alias, default và ví dụ](../../docs/CLI_USAGE.vi.md)
