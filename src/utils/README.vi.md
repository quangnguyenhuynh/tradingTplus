# Utility dùng chung

Các helper nhỏ dùng chung giữa package, không sở hữu ingest, persistence,
validation hoặc orchestration feature.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File và hợp đồng

- `time_utils.py` định nghĩa timezone thị trường `Asia/Ho_Chi_Minh`, trả về thời
  gian thị trường hiện tại có timezone và parse timestamp nguồn mà không thay
  giá trị sai bằng thời gian hiện tại.
- `__init__.py` đánh dấu thư mục này là Python package.

Caller phải giữ timestamp timezone-aware. Logic phiên có thể đổi timestamp UTC
sang giờ Việt Nam nhưng không được cộng tay bảy giờ hoặc dùng audit timestamp
thay cho thời gian nến nguồn.

Package này không gọi network và không đọc/ghi database.

## Kiểm tra

```bash
python -m compileall src/utils
python -m pytest -q tests/validation tests/features
```
