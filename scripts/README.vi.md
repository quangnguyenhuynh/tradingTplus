# Danh mục script vận hành

[English](README.md) · [CLI](../docs/CLI_USAGE.vi.md)

Chạy từ root sau khi cài requirements/venv. Bảng phân loại theo code thực tế, không theo tên thư mục. Không chạy lệnh WRITE để kiểm tra tài liệu. README từng thư mục dưới có ví dụ, tham số, dependency, output, exit và giới hạn an toàn.

| Công cụ | Mục đích | Phân loại | Dependency |
| --- | --- | --- | --- |
| [checks/check_ingest.py](checks/README.vi.md) | Kiểm tra completeness daily/intraday đã lưu | READ-ONLY — database read | Supabase |
| [checks/check_supabase.py](checks/README.vi.md) | Kiểm tra kết nối các bảng lõi | READ-ONLY — database read | SUPABASE_URL + SUPABASE_SERVICE_KEY |
| [checks/check_ssi_ingest_schema.py](checks/README.vi.md) | Select cột bắt buộc và in SQL kiểm tra constraint | READ-ONLY — database read | Supabase |
| [checks/phase0_validate_schema.py](checks/README.vi.md) | Kiểm tra catalog PostgreSQL bằng transaction chỉ đọc | READ-ONLY — database read | PHASE0_DATABASE_URL or --database-url |
| [checks/phase0_reconcile_sample.py](checks/README.vi.md) | Đối soát một mẫu raw/clean/feature có giới hạn | READ-ONLY — database read | Supabase |
| [checks/check_complete_ssi_ingest.py](checks/README.vi.md) | Smoke test SSI nhiều dataset trước đây; tắt do thiếu master | NOT_IMPLEMENTED | None / không có |
| [previews/run_features.py](previews/README.vi.md) | Gọi engine persist feature thủ công; có ghi dù nằm trong previews | WRITE — feature calculation | Supabase only / chỉ Supabase |
| [previews/eod_dry_run.py](previews/README.vi.md) | Chẩn đoán EOD kết hợp trước đây; tắt do stock_intraday | NOT_IMPLEMENTED | None / không có |
| [maintenance/fetch_one_day.py](maintenance/README.vi.md) | Chẩn đoán nguồn một mã/ngày trước đây; tắt do stock_intraday | NOT_IMPLEMENTED | None / không có |
| [capture/snapshot_stream.py](capture/README.vi.md) | Chụp stream giới hạn trước đây; tắt chờ protocol v3 được xác minh | NOT_IMPLEMENTED | None / không có |
| [capture/snapshot_orderbook.py](capture/README.vi.md) | Chụp depth trước đây; tắt chờ streaming v3 được xác minh | NOT_IMPLEMENTED | None / không có |
| [inspectors/ssi_streaming/inspect.py](inspectors/ssi_streaming/README.vi.md) | Inspector negotiate/run cũ; mọi subcommand kể cả list đều tắt | NOT_IMPLEMENTED | None / không có |
| [inspectors/ssi_rest/inspect.py](inspectors/ssi_rest/README.vi.md) | Xem SSI v3 raw/clean | READ-ONLY — SSI API request | SSI v3 (run) |
| [maintenance/backfill_stock_intraday_value.sql](maintenance/README.vi.md) | SQL sửa value không scope | WRITE — không chạy nguyên bản | PostgreSQL |

Module `__init__`, client, registry, datasets, endpoints, mapping, output là thư viện hỗ trợ, không phải CLI độc lập. run_features trong previews có ghi stock_features và không có dry-run: vấn đề tên/vị trí cần task code riêng. Không có thay đổi DB/migration/backfill từ task tài liệu.
