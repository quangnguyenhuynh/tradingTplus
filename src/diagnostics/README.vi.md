# src/diagnostics

Boundary chẩn đoán. Fetch/dry-run kết hợp daily và intraday trả unavailable trước khi gọi dịch vụ.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `eod_dry_run.py`
- `fetch_one_day.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
