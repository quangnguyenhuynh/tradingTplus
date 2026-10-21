# src/ingest/shared

Helper ngày, scope symbol/index và trạng thái pipeline; không gọi provider.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `date_utils.py`
- `index_scope.py`
- `pipeline_status.py`
- `symbol_scope.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
