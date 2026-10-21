# scripts/capture

NOT_IMPLEMENTED: snapshot stream/orderbook. Giữ parser nhưng trả FAILED/NOT_IMPLEMENTED, không truy cập SSI/Supabase.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `snapshot_orderbook.py`
- `snapshot_stream.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
