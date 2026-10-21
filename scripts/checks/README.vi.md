# checks — hướng dẫn công cụ

[English](README.md) · [CLI](../../docs/CLI_USAGE.vi.md)

Chạy tại root với venv Python 3.11 đã cài requirements. Ngày stock nhận DD/MM/YYYY hoặc ISO; riêng đối soát Phase 0 nhận ISO. Phân biệt kiểm tra parser với kết quả dữ liệu thật; các ví dụ chỉ kiểm tra offline. Script NOT_IMPLEMENTED giữ tham số để tương thích nhưng không gọi SSI/DB kể cả --write; help exit 0, gọi nghiệp vụ trả JSON FAILED/NOT_IMPLEMENTED exit 1.

## `scripts/checks/check_ingest.py`

Kiểm tra completeness daily/intraday đã lưu.

**READ-ONLY — database read**. Phụ thuộc: Supabase. Đầu ra: JSON; exit 0 after return; inspect JSON status / đọc trạng thái JSON.

```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--date` | required=True |
| `--symbols` | nargs='+', default=None |

## `scripts/checks/check_supabase.py`

Kiểm tra kết nối các bảng lõi.

**READ-ONLY — database read**. Phụ thuộc: SUPABASE_URL + SUPABASE_SERVICE_KEY. Đầu ra: Per-table PASS/FAIL; exit 0 pass, 1 failures, 2 missing config / thiếu cấu hình.

```bash
python scripts/checks/check_supabase.py
```

Không có tham số CLI; check_supabase không có help parser.

## `scripts/checks/check_ssi_ingest_schema.py`

Select cột bắt buộc và in SQL kiểm tra constraint.

**READ-ONLY — database read**. Phụ thuộc: Supabase. Đầu ra: Table/column PASS/FAIL; exit 1 failures, 0 otherwise / khi không lỗi.

```bash
python scripts/checks/check_ssi_ingest_schema.py
```

Không có tham số CLI; check_supabase không có help parser.

## `scripts/checks/phase0_validate_schema.py`

Kiểm tra catalog PostgreSQL bằng transaction chỉ đọc.

**READ-ONLY — database read**. Phụ thuộc: PHASE0_DATABASE_URL or --database-url. Đầu ra: JSON PASS/FAIL/UNKNOWN; exit 0/1/2.

```bash
python scripts/checks/phase0_validate_schema.py
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--database-url` | default=os.getenv('PHASE0_DATABASE_URL') |

## `scripts/checks/phase0_reconcile_sample.py`

Đối soát một mẫu raw/clean/feature có giới hạn.

**READ-ONLY — database read**. Phụ thuộc: Supabase. Đầu ra: Payload + reconciliation JSON; exit 1 FAIL, 2 UNKNOWN, 0 otherwise.

```bash
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 15m --tolerance 0.000001
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | required=True |
| `--date` | required=True |
| `--timeframe` | required=True, choices=('1d', '15m', '60m') |
| `--timestamp` |  |
| `--tolerance` | type=float, default=1e-06 |

## `scripts/checks/check_complete_ssi_ingest.py`

Smoke test SSI nhiều dataset trước đây; tắt do thiếu master.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/checks/check_complete_ssi_ingest.py --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | default='SSI' |
| `--date` | default=None |
| `--index-code` | default='VNINDEX' |
| `--write` | action='store_true' |
| `--write-intraday` | action='store_true' |
| `--force` | action='store_true' |

## Diễn giải và giới hạn

check_ingest không sửa dữ liệu; không dùng một số nến cố định làm bằng chứng đủ phiên. check_supabase chỉ select một hàng mỗi bảng, không kiểm tra unique index. check_ssi_ingest_schema còn dùng một số cột index/foreign cũ trước contract 2.0; có thể FAIL dù schema hiện tại đúng. Không tạo cột cũ để làm check pass; cần sửa diagnostic trong task code riêng. Phase 0 có thể UNKNOWN khi thiếu schema/nguồn; không nâng thành PASS. --timestamp tùy chọn giới hạn đúng hàng feature intraday, tolerance mặc định 1e-6. --database-url mặc định lấy PHASE0_DATABASE_URL; không đưa URL thật vào log hoặc lịch sử lệnh.

check_complete_ssi_ingest giữ --symbol (SSI), --date, --index-code (VNINDEX), --write, --write-intraday, --force nhưng tất cả nghiệp vụ bị tắt; không dùng nó để chứng minh ingest v3 hoạt động. Không có credential nào cần cho stub.
