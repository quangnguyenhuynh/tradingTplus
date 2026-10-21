# scripts/checks

Kiểm tra DB/schema/completeness tường minh, mặc định read-only. Smoke tool ingest kết hợp cũ trả unavailable.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `check_complete_ssi_ingest.py`
- `check_ingest.py`
- `check_ssi_ingest_schema.py`
- `check_supabase.py`
- `phase0_reconcile_sample.py`
- `phase0_validate_schema.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
