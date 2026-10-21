# previews — hướng dẫn công cụ

[English](README.md) · [CLI](../../docs/CLI_USAGE.vi.md)

Chạy tại root với venv Python 3.11 đã cài requirements. Ngày stock nhận DD/MM/YYYY hoặc ISO; riêng đối soát Phase 0 nhận ISO. Phân biệt kiểm tra parser với kết quả dữ liệu thật; các ví dụ chỉ kiểm tra offline. Script NOT_IMPLEMENTED giữ tham số để tương thích nhưng không gọi SSI/DB kể cả --write; help exit 0, gọi nghiệp vụ trả JSON FAILED/NOT_IMPLEMENTED exit 1.

## `scripts/previews/run_features.py`

Gọi engine persist feature thủ công; có ghi dù nằm trong previews.

**WRITE — feature calculation**. Phụ thuộc: Supabase only / chỉ Supabase. Đầu ra: Feature engine complete: N records; exit 0 after return, exceptions propagate / exception truyền ra.

```bash
python scripts/previews/run_features.py --mode incremental --symbols SSI --timeframes 1d
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--mode` | choices=['full', 'incremental'], default='incremental' |
| `--symbols` | nargs='*', default=None |
| `--timeframes` | nargs='*', default=list(DEFAULT_PERSISTED_FEATURE_TIMEFRAMES) |

## `scripts/previews/eod_dry_run.py`

Chẩn đoán EOD kết hợp trước đây; tắt do stock_intraday.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/previews/eod_dry_run.py --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--date` | default=None |
| `--symbols` | nargs='*', default=DEFAULT_SYMBOLS |
| `--timeframes` | nargs='*', default=DEFAULT_TIMEFRAMES |
| `--json` | action='store_true' |

## Lưu ý ghi dữ liệu

run_features ghi `stock_features`, đọc `stock_daily` cho 1d và clean `stock_intraday` 1m cho 15m/60m, có đọc ngữ cảnh daily. Không persist 1m/5m, không ghi lại nến aggregate. --mode mặc định incremental, symbols bỏ trống dùng phạm vi engine, timeframe mặc định 15m 60m 1d. Không có --date, --dry-run hay --apply; không chạy chỉ để preview. Đầu ra số record không xác minh completeness. Tên/vị trí previews gây hiểu nhầm là issue code riêng; task tài liệu không đổi script.

eod_dry_run giữ --date, --symbols (SSI HPG FPT), --timeframes (15m 60m 1d), --json nhưng không thực hiện dry-run nguồn hay tính feature. Cần adapter intraday v3 đã xác minh mới có thể khôi phục pipeline cũ.
