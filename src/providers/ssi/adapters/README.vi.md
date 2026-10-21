# src/providers/ssi/adapters

Chuyển payload provider thành AdapterResult theo mapping đã kiểm chứng; không import ingest/database.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `v3.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
