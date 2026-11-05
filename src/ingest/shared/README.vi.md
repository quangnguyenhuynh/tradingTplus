# src/ingest/shared

## Ownership backfill EOD — 05/11/2026

| Trách nhiệm | Module canonical |
| --- | --- |
| Stock runner + `_run_ingest_backfill` | `src/ingest/stock_daily/backfill.py` |
| Index runner | `src/ingest/index_daily/index_backfill.py` |
| Năm helper range/report dùng chung | `src/ingest/shared/backfill_range.py` |
| Intraday có guard và legacy compatibility | `src/ingest/maintenance/backfill.py` |

Stock/Index dùng helper shared trực tiếp. Maintenance re-export Stock runner và
các helper cũ, không nhân bản logic. Public import từ `src.ingest` vẫn giữ tên;
lazy export Stock nay trỏ về domain Stock. CLI handler vẫn dùng public export.
Không đổi CLI/options/JSON flow, thuật toán, policy, persistence hoặc guards.
Refactor này không cần migration, không sửa dữ liệu hoặc yêu cầu backfill.

[Báo cáo chuyển module, compatibility và kiểm chứng](../../../docs/backfill/README.vi.md).


Helper ngày, scope symbol/index và trạng thái pipeline; không gọi provider.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `backfill_range.py`
- `date_utils.py`
- `index_scope.py`
- `pipeline_status.py`
- `symbol_scope.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.
