# maintenance — hướng dẫn công cụ

[English](README.md) · [CLI](../../docs/CLI_USAGE.vi.md)

Chạy tại root với venv Python 3.11 đã cài requirements. Ngày stock nhận DD/MM/YYYY hoặc ISO; riêng đối soát Phase 0 nhận ISO. Phân biệt kiểm tra parser với kết quả dữ liệu thật; các ví dụ chỉ kiểm tra offline. Script NOT_IMPLEMENTED giữ tham số để tương thích nhưng không gọi SSI/DB kể cả --write; help exit 0, gọi nghiệp vụ trả JSON FAILED/NOT_IMPLEMENTED exit 1.

## `scripts/maintenance/fetch_one_day.py`

Chẩn đoán nguồn một mã/ngày trước đây; tắt do stock_intraday.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/maintenance/fetch_one_day.py --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | required=True |
| `--date` | required=True |
| `--dry-run` | action='store_true', default=True |
| `--write` | action='store_true' |

## `scripts/maintenance/backfill_stock_intraday_value.sql`

**WRITE — bảo trì rộng, không giới hạn mã/ngày. Không phải CLI production an toàn.** SQL hiện tại cập nhật tất cả hàng stock_intraday có value null khi close/volume khác null, dùng close * volume. Không có cờ, không có scope hoặc xác nhận. Giá trị đó là ước tính, không phải turnover sàn; cần giữ null với input sai và đối chiếu quy tắc làm tròn hiện hành. Không chạy file nguyên bản. Cần task sửa chữa được review riêng với phạm vi, số hàng trước/sau, backup/rollback và quyền PostgreSQL phù hợp. Task tài liệu không thực thi SQL hay yêu cầu backfill.

fetch_one_day giữ cặp --symbol/--date bắt buộc và cặp loại trừ --dry-run/--write; vẫn trả NOT_IMPLEMENTED trước mọi truy cập. --write không bật lại nguồn intraday. Lịch sử clean vẫn có thể dùng cho feature.
