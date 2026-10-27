# src/providers/ssi/adapters

Chuyển payload provider thành AdapterResult theo mapping đã kiểm chứng; không import ingest/database.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `v3.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Master chứng khoán đã xác minh

master_v3 dùng chung fetch/map securitiesByBoard cho HOSE/HNX/UPCOM. Symbols/securities READY có guard; hai capability index giữ nguyên BLOCKED. Không total authoritative, completeness thị trường UNVERIFIED. Giữ mọi loại chứng khoán, không tự bật eligibility. [Mapping, guard, bằng chứng và recovery](../../../ingest/master/README.vi.md).

## Cutover master hợp nhất — 27/10/2026

Phần này thay thế hướng dẫn cũ sync symbols/securities độc lập: chỉ symbols là đích vật lý; securities là alias deprecated có warning, all chỉ chạy symbols một lần. Owner apply A expand/merge TRƯỚC deploy app; B retire riêng có approval, mặc định abort. Agent không apply production. VN50 GROWTH được loại đúng rule và đếm; HNX-request DERIVATIVES/Future giữ domain thật và inactive mặc định. Index vẫn BLOCKED; không backfill giá. [Runbook](../../../ingest/master/README.vi.md).
