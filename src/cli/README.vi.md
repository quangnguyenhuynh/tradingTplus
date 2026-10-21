# src/cli

Parse tham số, kiểm tra source/capability trước I/O và điều phối CLI theo domain. Lệnh bị vô hiệu hóa trả FAILED/NOT_IMPLEMENTED, exit 1.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `analogs.py`
- `common.py`
- `features.py`
- `foreign.py`
- `index.py`
- `maintenance.py`
- `parser.py`
- `screener.py`
- `stock.py`
- `streaming.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
