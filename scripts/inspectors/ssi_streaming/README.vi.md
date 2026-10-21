# inspectors/ssi_streaming — hướng dẫn công cụ

[English](README.md) · [CLI](../../../docs/CLI_USAGE.vi.md)

Chạy tại root với venv Python 3.11 đã cài requirements. Ngày stock nhận DD/MM/YYYY hoặc ISO; riêng đối soát Phase 0 nhận ISO. Phân biệt kiểm tra parser với kết quả dữ liệu thật; các ví dụ chỉ kiểm tra offline. Script NOT_IMPLEMENTED giữ tham số để tương thích nhưng không gọi SSI/DB kể cả --write; help exit 0, gọi nghiệp vụ trả JSON FAILED/NOT_IMPLEMENTED exit 1.

## `scripts/inspectors/ssi_streaming/inspect.py`

Inspector negotiate/run cũ; mọi subcommand kể cả list đều tắt.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python -m scripts.inspectors.ssi_streaming.inspect --help
python -m scripts.inspectors.ssi_streaming.inspect run --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--timeout` | type=int, default=30 |
| `kind` | choices=[*STREAM_TYPES.keys(), 'all'] |
| `--symbols` | nargs='+', default=['SSI'] |
| `--index-codes` | nargs='+', default=['VNINDEX'] |
| `--timeout` | type=int, default=30 |
| `--max-messages` | type=int, default=3 |
| `--limit` | type=int, default=None |
| `--full-json` | action='store_true' |
| `--raw-frames` | action='store_true' |
| `--channel` |  |
| `--negotiate-only` | action='store_true' |

## Subcommand đang tắt

`list`, `negotiate` và `run` đều trả NOT_IMPLEMENTED, kể cả list không kết nối. negotiate có timeout mặc định 30. run giữ kind theo registry (hoặc all), symbols mặc định SSI, index-codes VNINDEX, timeout 30, max-messages 3, limit tùy chọn, full-json/raw-frames/channel/negotiate-only. Những tên loại payload cũ không chứng minh protocol v3 hoạt động. Không cần SSI/Supabase credential vì không gọi dịch vụ. Chỉ sau adapter streaming v3 được xác minh mới xem xét bật lại.

## BLOCKED: chạy bằng đường dẫn trực tiếp

`python scripts/inspectors/ssi_streaming/inspect.py --help` hiện gây ImportError trước parse do inspect.py che module inspect chuẩn, dẫn tới circular import STREAM_TYPES. Dùng module invocation dưới đây để help chạy local; nghiệp vụ vẫn trả NOT_IMPLEMENTED exit 1, không gọi SSI/DB. Cần sửa import/path trong task code riêng.

```bash
python -m scripts.inspectors.ssi_streaming.inspect --help
python -m scripts.inspectors.ssi_streaming.inspect run --help
```

Kind parser còn nhận `securities-status`, `quote`, `trade`, `foreign-room`, `index`, `realtime-bar`, `all`; đó chỉ là giá trị tương thích, không bật ingest.
