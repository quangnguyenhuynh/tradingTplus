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

Ứng dụng Python không tự động áp dụng migration trong repo. Chủ dự án đã apply
SQL 20260802 và 20260803 thủ công qua Supabase SQL Editor và kiểm tra schema
production kỳ vọng bằng query chỉ đọc. Trạng thái Phase 0 là
`PASS_WITH_MANUAL_APPLY_NOTE`. Supabase CLI migration history có thể thiếu hai
record này; không rerun hoặc repair chỉ để bổ sung history.

## An toàn

Không chạy SQL destructive diện rộng khi chưa có phạm vi table/date/symbol chính xác, phương án backup và task rõ ràng. Không giả định schema production đã giống migration mới nhất nếu chưa kiểm tra.

## Storage signal/backtest đã retire

`20260731_drop_legacy_signal_backtest.sql` là migration cleanup đã được phê duyệt rõ ràng. Migration chỉ destructive với hai bảng legacy đã retire; export row trước deployment nếu cần lưu audit. Raw, clean và feature data không bị ảnh hưởng, và không cần backfill.
## Storage Phase 1 kiểu rule đã retire

Hai file `20260804` và `20260806` chỉ được giữ làm deployment history bất biến;
không apply chúng trên môi trường mới. `20260810_drop_fixed_rule_phase1.sql` xóa
đúng sáu bảng đã retire theo thứ tự dependency ngược. Migration chạy thủ công và
mang tính destructive: export evidence cần giữ trước khi apply. Không cần
backfill source, feature hoặc Analog.

## 20260809 Historical Analog EOD V1

`20260809_create_historical_analog_core_eod_v1.sql` tạo thêm bảy bảng evidence
Analog Phase 1. Chạy migration thủ công, rồi chạy kiểm tra read-only tại
`sql/analogs/verify_historical_analog_core_eod_v1.sql`. Hướng dẫn cleanup và cảnh
báo lock/mất dữ liệu nằm tại `sql/analogs/README.md`.

## 20260811 Recovery Historical Analog và RPC runtime

Với cài đặt mới, chạy bản đã sửa `20260809_create_historical_analog_core_eod_v1.sql`. File dùng helper immutable `analog_jsonb_object_size(jsonb)` thay cho hàm không tồn tại `jsonb_object_length(jsonb)`, đồng thời giữ nguyên CHECK đúng chín dimension. Nếu script 20260809 cũ đã dừng giữa chừng, hãy chạy `20260811_recover_historical_analog_core_eod_v1.sql` (hoặc chạy ngay sau đó): migration idempotent, giữ nguyên row Analog đã có, hoàn thiện table/index/RLS/grant/policy còn thiếu và cài RPC transactional `persist_analog_query_v1(jsonb,jsonb)` chỉ cho service role. Sau đó chạy verification SQL read-only. Hai migration không đổi bảng Phase 0 và không backfill evidence.
