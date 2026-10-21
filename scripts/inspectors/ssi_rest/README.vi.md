# scripts/inspectors/ssi_rest

Inspector SSI v3 read-only theo endpoint hoặc dataset canonical; hiển thị raw, mapping report và clean preview. Không có xác thực/endpoint v2. Dataset preview không đồng nghĩa production-ready.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `client.py`
- `datasets.py`
- `endpoints.py`
- `inspect.py`
- `mapping.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
