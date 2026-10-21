# src/ingest/maintenance

Backfill daily riêng vẫn hoạt động. Backfill intraday, backfill kết hợp và refill bị chặn trước mọi stage.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `backfill.py`
- `refill.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
