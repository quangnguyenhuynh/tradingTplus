# scripts/maintenance

Fetch một ngày kết hợp trả unavailable. Artifact SQL bảo trì hiện có chỉ dành cho operator và không tự động thực thi.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `fetch_one_day.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
