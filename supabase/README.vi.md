# Cấu hình dự án Supabase

Cấu hình Supabase CLI local cho repository này.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Nội dung

- `config.toml`: thiết lập dự án cho Supabase CLI.

Migration ứng dụng có version hiện nằm trong folder root [`migrations/`](../migrations/README.vi.md), còn schema tham chiếu nằm ở `schema.sql` tại root repository.

## Quy tắc

- Không commit service-role key, mật khẩu database, access token hoặc file `.env` sinh ra.
- Không xem cấu hình CLI local là bằng chứng schema production đã deploy.
- Rà soát thứ tự migration và đúng project trước khi link, push, reset hoặc áp dụng schema.
- Command Supabase destructive cần task rõ ràng, phương án backup/rollback và đánh giá ảnh hưởng.

Chạy schema check read-only trước mọi smoke write SSI hoặc backfill có phạm vi.
