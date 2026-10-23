# src/quality

Validation và completeness độc lập provider; không tạo candle giả hay tự tính feature.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Chẩn đoán Phase 0 SSI v3

`phase0.py` kiểm catalog bảng canonical và RPC security, rồi đối soát persisted 1m/1d/15m/60m. 1m không cần feature. Chỉ map source ssi_v3; legacy/NULL/ambiguous báo UNKNOWN, mâu thuẫn thật FAIL. Volume/value nguyên chính xác, không fallback/zero fill. Reuse aggregation thuần khi đủ evidence, không tính/persist feature. Mọi thao tác chỉ SELECT, có scope/bound; không migration, thay dữ liệu hoặc backfill. [Runbook](../../scripts/checks/README.vi.md).
