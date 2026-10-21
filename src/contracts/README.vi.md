# src/contracts

Hợp đồng canonical, engine mapping, transform và từ điển source tách biệt; engine không chứa chi tiết endpoint.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `derived.py`
- `engine.py`
- `registry.py`
- `transforms.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
