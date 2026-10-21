# scripts/inspectors/ssi_streaming

NOT_IMPLEMENTED: inspector kết nối streaming. Vẫn giữ utility decode frame lịch sử offline, không có client kết nối.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `inspect.py`
- `output.py`
- `registry.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
