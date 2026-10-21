# src/ingest/index_daily

ACTIVE: ingest/backfill/preview Index Daily qua SSI v3 indexSummary; dùng index_master hiện có, không tự sync master.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `index_backfill.py`
- `index_daily.py`
- `index_daily_fetcher.py`
- `index_daily_mapper.py`
- `index_daily_persistence.py`
- `index_daily_preview.py`
- `index_daily_service.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
