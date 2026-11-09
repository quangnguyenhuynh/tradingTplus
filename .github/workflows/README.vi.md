# GitHub Actions — TradingTPlus

## Các workflow EOD đang hoạt động

| Workflow | Lịch giờ Việt Nam | Cron UTC | Ngày dữ liệu được truyền tường minh |
| --- | --- | --- | --- |
| `stock-eod-scheduled.yml` | 17:07 thứ Hai–thứ Sáu | `7 10 * * 1-5` | Chính ngày chạy tại Việt Nam |
| `index-eod-scheduled.yml` | 08:07 thứ Ba–thứ Bảy | `7 1 * * 2-6` | Ngày lịch trước đó tại Việt Nam |

Hai file mới thay thế `stock-eod.yml` và `index-eod-v2.yml` đã nghỉ. GitHub cron dùng **UTC**, Việt Nam UTC+7 và không có DST. GitHub Actions có thể khởi chạy trễ. Để tránh ghi nhầm phiên, job lấy **mốc lịch Việt Nam gần nhất đã qua**, kể cả khi GitHub khởi chạy sau nửa đêm hoặc cuối tuần. Stock dùng ngày của mốc lịch; Index dùng ngày trước mốc lịch. Log ghi `expected_slot_vn`, `runtime_vn`, `target_date`, `target_source`. Nếu job trễ qua **mốc lịch kế tiếp**, chỉ dựa vào giờ chạy thực tế không thể nhận diện chắc chắn phiên gốc, có thể chọn mốc mới; cần kiểm tra log và chạy tay với ngày tường minh để khôi phục phiên bỏ lỡ. GitHub bỏ hẳn cron không được tự khôi phục; không tự backfill hoặc dò ngày lễ. SSI trả rỗng không được tạo dữ liệu giả.

Với lịch tự động, workflow tính ngày mục tiêu và truyền ngày tường minh vào `python main.py stock-eod` hoặc `python main.py index-eod`. Chạy thủ công có nhập `date` dùng đúng ngày nhập; chạy thủ công để trống `date` sẽ gọi CLI **không kèm ngày**, vì vậy giữ nguyên hành vi mặc định của code hiện tại. Không sửa code ingest hoặc `src.ingest.workflows.workflow_dates`.

**Lưu ý:** Đây là **mỗi pipeline chạy một lần cho một phiên**, không phải hai lượt retry của cùng một dataset: Stock chạy chiều phiên T, Index chạy sáng ngày kế tiếp. Lịch giả định thị trường giao dịch thứ Hai–thứ Sáu, không tự kiểm tra ngày lễ, SSI đã đủ dữ liệu hay chưa. Stock EOD vẫn chạy completeness hiện có. Khi cần lấy lại cùng phiên, chạy lại có chủ đích theo ngày; quy tắc ghi lại raw/clean giữ nguyên.

Các workflow khác (`features.yml`, `tests.yml`, `stock-intraday.yml`) không thay đổi. Không tự chạy feature/signal/backtest hoặc gọi chéo Stock/Index.

Không migration, không sửa DB và không yêu cầu backfill lịch sử trong thay đổi workflow này.
