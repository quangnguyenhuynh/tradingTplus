# src/quality/validators

Validation bản ghi canonical, logging và kiểm tra Phase 0 giới hạn/read-only. Raw thuộc source đã retire không được remap bằng v3.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `daily_validator.py`
- `index_daily_validator.py`
- `intraday_validator.py`
- `logging_utils.py`
- `models.py`
- `phase0.py`
- `streaming_validator.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
