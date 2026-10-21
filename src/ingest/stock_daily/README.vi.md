# src/ingest/stock_daily

ACTIVE: ingest Stock Daily qua SSI v3 securitiesSummary; giữ nguyên raw payload, hash, provenance và validation.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `daily.py`
- `daily_fetcher.py`
- `daily_mapper.py`
- `daily_persistence.py`
- `daily_service.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
