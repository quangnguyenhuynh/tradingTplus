# Truy cập database

Supabase client và các helper persistence của repository.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## File chính

- `client.py`: khởi tạo Supabase client và cung cấp helper đọc/insert/upsert theo bảng.
- `__init__.py`: export package.

## Trách nhiệm

- Đọc master, raw, clean, feature và snapshot data cho các pipeline hiện tại.
- Ghi record theo đúng hợp đồng table và conflict key.
- Trả lỗi có ngữ cảnh thay vì nuốt lỗi database.
- Lấy credential từ biến môi trường và không in ra log.

## Ranh giới

- Package này không định nghĩa hoặc tự migrate schema.
- Thay đổi schema thuộc [`migrations/`](../../migrations/README.vi.md).
- Trước khi thêm `upsert`, phải xác nhận unique index tương ứng tồn tại.
- Không fallback sang cách ghi tạo duplicate chỉ để job tiếp tục chạy.
- Không đổi field thị trường thiếu thành 0 nếu chưa có quy tắc đã kiểm chứng.

## Test

Unit test nên mock Supabase client. Smoke test live mặc định read-only và chạy qua các script như `scripts/check_supabase.py` và `scripts/check_ssi_ingest_schema.py`.

## Adapter Phase 1
`phase1.py` là repository boundary cho các bảng fixed-rule strategy, setup,
signal, backtest và review đang chạy được. Adapter này đang đóng băng/đã bị thay
thế, không phải persistence layer historical analog mới. Nó vẫn không ghi raw,
clean hoặc feature. Các bảng analog đề xuất cần migration riêng được review và
không được âm thầm repurpose bảng cũ.
