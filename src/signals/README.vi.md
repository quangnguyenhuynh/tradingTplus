# Signal

Daily setup chỉ tạo candidate. Scanner chỉ đọc feature nến đã đóng tại hoặc trước cutoff; chỉ đúng strategy version/config đã approve mới được ghi signal thật.

### CLI Phase 1 vận hành (2026-08-06)
Các lệnh database-backed đã chạy được và tách khỏi ingest/features. Mặc định dry-run; ghi phải có `--write`. Setup/signal production yêu cầu đúng strategy version/config đã approve. Phiên lịch sử lấy từ `stock_daily` quan sát; setup live bắt buộc target session explicit. Unique first-match chỉ cho một signal mỗi strategy/config/symbol/phiên. Khi đổi rule/evaluator phải tăng version và tạo evidence mới.
