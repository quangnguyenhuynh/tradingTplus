# src/providers/ssi/adapters

Chuyển payload provider thành AdapterResult theo mapping đã kiểm chứng; không import ingest/database.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `v3.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Registry master

Contract/registry master tách khỏi readiness daily/intraday. Cả bốn dataset SSI v3 BLOCKED; không triển khai v4/v5 giả, chưa xác minh field master. [Contract, cách thêm version và audit](../../../ingest/master/README.vi.md).
