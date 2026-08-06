# Strategy

Rule hai bước, bất biến và có version. Mọi lần đánh giá trả `RuleDecision` để audit. Đổi threshold phải tạo version và evidence mới.

### CLI Phase 1 vận hành (2026-08-06)
Các lệnh database-backed đã chạy được và tách khỏi ingest/features. Mặc định dry-run; ghi phải có `--write`. Setup/signal production yêu cầu đúng strategy version/config đã approve. Phiên lịch sử lấy từ `stock_daily` quan sát; setup live bắt buộc target session explicit. Unique first-match chỉ cho một signal mỗi strategy/config/symbol/phiên. Khi đổi rule/evaluator phải tăng version và tạo evidence mới.
