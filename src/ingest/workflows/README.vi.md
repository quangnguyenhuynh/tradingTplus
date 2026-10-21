# src/ingest/workflows

Điều phối Stock EOD và xác định ngày workflow. Workflow ingest intraday trả unavailable trước I/O.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `stock_eod.py`
- `stock_intraday.py`
- `workflow_dates.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
