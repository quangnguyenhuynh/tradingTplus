# capture — hướng dẫn công cụ

[English](README.md) · [CLI](../../docs/CLI_USAGE.vi.md)

Chạy tại root với venv Python 3.11 đã cài requirements. Ngày stock nhận DD/MM/YYYY hoặc ISO; riêng đối soát Phase 0 nhận ISO. Phân biệt kiểm tra parser với kết quả dữ liệu thật; các ví dụ chỉ kiểm tra offline. Script NOT_IMPLEMENTED giữ tham số để tương thích nhưng không gọi SSI/DB kể cả --write; help exit 0, gọi nghiệp vụ trả JSON FAILED/NOT_IMPLEMENTED exit 1.

## `scripts/capture/snapshot_stream.py`

Chụp stream giới hạn trước đây; tắt chờ protocol v3 được xác minh.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/capture/snapshot_stream.py --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--symbols` | nargs='*', default=None |
| `--indexes` | nargs='*', default=['VNINDEX', 'VN30'] |
| `--timeout` | type=int, default=60 |
| `--limit` | type=int, default=20 |
| `--debug` | action='store_true' |
| `--write` | action='store_true', default=False |

## `scripts/capture/snapshot_orderbook.py`

Chụp depth trước đây; tắt chờ streaming v3 được xác minh.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/capture/snapshot_orderbook.py --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `symbols` | nargs='*' |
| `--timeout` | type=int, default=None |
| `--debug` | action='store_true' |
| `--write` | action='store_true', default=False |
| `--no-write` | action='store_true' |

## Khôi phục trong tương lai

snapshot_stream giữ symbols, indexes mặc định VNINDEX VN30, timeout 60, limit 20, debug/write. snapshot_orderbook dùng mã positional, timeout tùy chọn, debug và cặp loại trừ --write/--no-write. Cả hai không có kết nối streaming v3, không ghi stream_* hay stock_orderbook_snapshot. Không coi help cũ là hỗ trợ production; cần adapter protocol/auth/timestamp/session đã xác minh. Không có REST depth công khai được suy diễn. Dữ liệu snapshot lịch sử vẫn còn nguyên.
