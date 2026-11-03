# src/quality/validators

## Stock Daily Data Quality V1 — 03/11/2026

SSI v3 Stock Daily dùng VALID/PARTIAL/REJECTED, quarantine optional lỗi thành NULL,
giữ RAW bất biến và log hiện tại/lịch sử. Cần owner apply migration
`20261103_stock_daily_quality_v1.sql` trước writer mới; status lịch sử giữ NULL.
Diagnostic chỉ đọc mới: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Giữ tên `stock-eod`/`stock-eod-backfill`; không tự backfill/features.
[Policy, triển khai, SQL kiểm tra và rerun đúng scope](../../../docs/STOCK_DAILY_QUALITY_V1.vi.md).


Validation bản ghi canonical, logging và kiểm tra Phase 0 giới hạn/read-only. Raw thuộc source đã retire không được remap bằng v3.

Việc di chuyển code trước đây không đổi schema/công thức/profile/provenance. Stock Daily V1 cần migration nêu trên; rerun dữ liệu luôn tường minh.

Các module:

- `daily_validator.py`
- `index_daily_validator.py`
- `intraday_validator.py`
- `logging_utils.py`
- `models.py`
- `phase0.py`
- `streaming_validator.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Chẩn đoán Phase 0 SSI v3

`phase0.py` kiểm catalog bảng canonical và RPC security, rồi đối soát persisted 1m/1d/15m/60m. 1m không cần feature. Chỉ map source ssi_v3; legacy/NULL/ambiguous báo UNKNOWN, mâu thuẫn thật FAIL. Volume/value nguyên chính xác, không fallback/zero fill. Reuse aggregation thuần khi đủ evidence, không tính/persist feature. Mọi thao tác chỉ SELECT, có scope/bound; không migration, thay dữ liệu hoặc backfill. [Runbook](../../../scripts/checks/README.vi.md).
