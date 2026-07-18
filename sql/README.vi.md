# SQL vận hành

Các tiện ích SQL chạy tường minh, không thuộc chuỗi migration có version.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Nội dung hiện tại

- `cleanup_accidental_ssi_smoke_records.sql`: template dọn các dòng smoke test ghi nhầm với phạm vi hẹp.

## An toàn

File trong folder này có thể xoá hoặc sửa dữ liệu. Không chạy nguyên trạng trên production khi chưa rà soát và thay mọi placeholder phạm vi.

Trước khi chạy:

1. Xác định đúng table, symbol và trading date.
2. Chạy câu `SELECT` tương đương và ghi nhận số dòng.
3. Dùng transaction khi phù hợp.
4. Kiểm tra lại dữ liệu ngay sau khi chạy.
5. Tách cleanup khỏi migration và pipeline ingest/backfill bình thường.

Không dùng cleanup SQL để thay thế việc sửa idempotency, validation hoặc mapping ingest sai.
