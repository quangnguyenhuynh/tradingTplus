# src/quality/completeness

Kiểm tra completeness dữ liệu đã lưu theo ngày/domain; không dùng một số candle cố định cho mọi phiên.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `index_completeness.py`
- `ingest_check.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
