# Database migrations

## 20260803 payload nguồn intraday thô

`20260803_add_raw_intraday_payload.sql` thêm cột nullable
`raw_intraday.payload JSONB` để ingest mới giữ toàn bộ object candle SSI theo
ngữ nghĩa JSON. Dữ liệu lịch sử tiếp tục là `NULL`; migration không dựng payload
giả, không backfill và không tạo GIN index. SQL kiểm tra/rollback nằm trong file
migration.

Các thay đổi SQL có version cho schema Supabase/PostgreSQL của Trading T+.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Hợp đồng

- Mọi thay đổi schema phải có migration.
- Migration nên additive và idempotent khi phù hợp.
- Giữ dữ liệu hiện có; không âm thầm drop, truncate hoặc nạp lại bảng production.
- Tạo unique index phù hợp với các `on_conflict` mà code sử dụng.
- Có SQL verification và ghi rõ rủi ro backfill, lock hoặc deployment.
- Tên file theo quy ước prefix ngày hiện có.

## Cách dùng

1. Đọc `schema.sql`, migration liên quan, query trong code và test.
2. Đối chiếu migration với schema Supabase mục tiêu.
3. Áp dụng tường minh qua quy trình deployment được chấp nhận hoặc Supabase SQL editor.
4. Chạy schema verification và smoke check read-only.
5. Thực hiện backfill cần thiết bằng thao tác riêng, có phạm vi.

Ứng dụng Python không tự động áp dụng các migration trong repo.

## An toàn

Không chạy SQL destructive diện rộng khi chưa có phạm vi table/date/symbol chính xác, phương án backup và task rõ ràng. Không giả định schema production đã giống migration mới nhất nếu chưa kiểm tra.

## Storage signal/backtest đã retire

`20260731_drop_legacy_signal_backtest.sql` là migration cleanup đã được phê duyệt rõ ràng. Migration chỉ destructive với hai bảng legacy đã retire; export row trước deployment nếu cần lưu audit. Raw, clean và feature data không bị ảnh hưởng, và không cần backfill.
