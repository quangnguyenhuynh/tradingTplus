# Data Quality V1 cho Stock Daily

[English](STOCK_DAILY_QUALITY_V1.md)

## Điều tra và phạm vi

Đã đọc `dev` tại `6284b4f4273df7e10c3a10b571ef4bb80a3bfe69` trước khi sửa. Mapper loại toàn bộ candidate khi bất kỳ field nào lỗi, kể cả optional `foreign_remaining_room: BELOW_MINIMUM`. Validator daily chỉ ghi application log. Runner stock backfill bỏ qua lỗi nằm trong ingest summary trả về, dẫn tới FAILED nhưng top-level không có lỗi. Vì vậy chưa thể lưu CLEAN một phần an toàn hoặc truy vấn lý do bền vững.

Đã kiểm tra catalog Supabase chỉ đọc cho ba bảng thực tế `stock_daily`, `stock_raw_daily`, `stock_data_quality_logs`, unique key CLEAN `(symbol,trading_date)`, RAW `(symbol,trading_date,source,data_hash)`, log `(symbol,trading_date,check_name)` và quyền bảng/sequence của service_role. Không đọc hoặc ghi row thị trường production. Owner xác nhận TCB lỗi ngày 05/03/2026 và 06/03/2026; fixture dùng hình dạng payload v3 thực tế có sẵn với room `-1` minh họa, không phải bản chép payload TCB. Không có SSI credentials, không gọi SSI live.

Chỉ thay đổi SSI v3 Stock Daily. Không đổi index/intraday, contracts/mappings, công thức features, tên EOD hiện tại hoặc exit policy. MappingResult chỉ bổ sung `partial_candidate`; mapping thông thường vẫn strict. Không thêm dependency hoặc bảng mới.

## Policy `stock_daily_validation_v1.0.0`

| Kết quả | CLEAN | Quality log |
| --- | --- | --- |
| VALID | Lưu `validation_status=VALID` | Không tạo issue mới; resolve issue V1 cũ nếu có |
| PARTIAL | Giữ field hợp lệ, quarantine field lỗi thành NULL, lưu `validation_status=PARTIAL` | ACTIVE |
| REJECTED | Không insert/overwrite CLEAN | ACTIVE rejection, giữ RAW |
| NULL lịch sử | Chưa được revalidate theo V1 | Không tự coi là VALID |

Symbol/date bắt buộc khớp request. OHLC phải parse được, hữu hạn, dương và đúng quan hệ high/low. Thiếu, bằng 0 hoặc âm đều reject; không dựng giá cho ngày không giao dịch. Match volume/value có giá trị phải parse được, hữu hạn, không âm. Thiếu `total_match_vol`/`total_match_val` giữ NULL, thêm warning và PARTIAL theo contract nullable hiện có. Match bằng 0 tường minh cùng OHLC hợp lệ dương có thể pass; thiếu match không đồng nghĩa 0 hoặc xác nhận phiên không giao dịch. Integer được kiểm tra chính xác, kể cả số lẻ và alias khác nhau.

Allowlist optional tường minh: `price_change`, `per_price_change`, `average_price`, `foreign_remaining_room`, `foreign_total_room`, `foreign_buy_vol_total`, `foreign_sell_vol_total`, `foreign_buy_val_total`, `foreign_sell_val_total`, `total_deal_vol`, `total_deal_val`, `total_buy_trade`, `total_buy_trade_vol`, `total_sell_trade`, `total_sell_trade_vol`.

Chỉ `BELOW_MINIMUM` và `TRANSFORM_ERROR` không mơ hồ trên allowlist được SET_NULL. Thiếu optional đã mapping tạo warning `MISSING_OPTIONAL`/KEEP_NULL. Các mã validator hiện có `DAILY_NON_POSITIVE_PRICE`, `DAILY_PRICE_CHANGE_MISMATCH`, `DAILY_PERCENT_CHANGE_MISMATCH` chỉ recover khi field thuộc allowlist. Alias có giá trị khác nhau, lỗi alias không xác định được, config mapping sai, lỗi cấu trúc chưa phân loại, nhiều record và identity không khớp đều reject. Field không được source/mapping hỗ trợ không tạo warning thiếu dữ liệu. Không nới contract số toàn cục.

`remainForeignRoom` âm giữ nguyên nghĩa mapping và giá trị RAW, chỉ đặt NULL trong CLEAN, giữ mã BELOW_MINIMUM. Đây là quarantine, không kết luận về ngữ nghĩa SSI. `total_traded_vol`, `total_traded_value`, `net_foreign_vol`, `net_foreign_val` cần đủ hai input; input NULL/quarantine làm derived NULL. Không điền 0 giả.

## Persistence và provenance

Adapter dùng policy thuần; service lưu RAW bất biến trước rồi gọi `persist_stock_daily_validation_v1` đúng một lần. RPC khóa `(symbol,date)`, merge CLEAN, ghi/resolve log hiện có và readback hai phần trong cùng transaction. SECURITY INVOKER, search_path rỗng, chỉ service_role có execute; giữ nguyên quyền bảng/RLS. Ack sai, thiếu migration, lỗi log hoặc trigger bỏ qua write đều làm processing thất bại. Không tự retry RPC sau response mơ hồ. RAW commit riêng nên có thể tồn tại khi CLEAN chưa có; phải inspect/reconcile trước rerun. HTTP mất ack có thể xảy ra sau commit; CLI báo thất bại thay vì khẳng định thành công.

REJECTED không ghi đè CLEAN. CLEAN đã VALID gặp source PARTIAL sẽ REJECTED với `CLEAN_VALID_DOWNGRADE_BLOCKED`, giữ nguyên row VALID. Với write khác được chấp nhận, NULL mới không xóa input số cũ hợp lệ. Không giữ giá trị legacy sai (âm/không hữu hạn/số lẻ trong field integer); derived luôn tính lại, không đưa vào preserved_fields. `preserved_fields`, action KEEP_EXISTING_FIELD và `previous_clean_raw_hash` giải thích evidence giữ lại; derived tính lại từ input cuối cùng, vẫn truyền NULL. Field giữ lại có thể đến từ RAW trước thay vì payload hiện tại. Hash trước có thể NULL nếu provenance lịch sử không thể truy ngược. Payload mới đủ điều kiện và không issue nâng PARTIAL thành VALID. Giữ `created_at` cũ, cập nhật `updated_at` từ audit time của ứng dụng.

## Issue hiện tại và lịch sử

Identity cố định `(symbol,trading_date,check_name='stock_daily_validation_v1')`, timeframe `1d`: một row hiện tại, không tạo row cho từng lần chạy. ACTIVE mô tả lần thử mới nhất, có thể cùng tồn tại với CLEAN VALID được bảo vệ. RESOLVED là lần revalidate được chấp nhận mới nhất không còn issue; không xóa lịch sử.

`details` chứa dataset/source, RAW SHA256, version policy/mapping/contract, quyết định source/cuối cùng, thời điểm đánh giá, issues, preserved_fields, hash RAW của CLEAN trước, clean_persistence_permitted, fingerprint xác định và history. Mỗi issue có field/code/severity/action/message, ví dụ:

```json
{"field":"foreign_remaining_room","code":"BELOW_MINIMUM","severity":"ERROR","action":"SET_NULL","message":"Value below the allowed minimum"}
```

Không chép toàn payload RAW vào log. Fingerprint bao gồm RAW hash, policy, quyết định cuối, issues và preserved_fields. Replay giống nhau chỉ cập nhật trạng thái hiện tại; snapshot cũ khác fingerprint được thêm history đúng một lần. Lặp xen kẽ các kết quả đã biết không tăng vô hạn bản sao history. RAW/issue mới khác nhau vẫn có thể tăng history; cần theo dõi dung lượng. Resolve giữ snapshot lỗi trong history, status RESOLVED/count 0. VALID chưa từng có issue không tạo log.

## Diagnostic chỉ đọc

```bash
python main.py stock-eod-quality --symbols TCB --date 05/03/2026
python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing > tcb-quality.json
```

Chỉ đọc RAW/CLEAN đã lưu, không gọi SSI hoặc ghi DB/log/features; dùng cùng policy ingest. Giới hạn 1–50 mã tường minh, tối đa 31 ngày lịch, page 100 row và tối đa 10.000 row/bảng; kiểm tra identity/order/count ổn định. Thu hẹp scope khi chạm cap hoặc count thay đổi. JSON gồm lỗi mapping/policy, quyết định replay, CLEAN presence, validation_status nullable đã lưu và thống kê field/code. Replay là dự đoán cho một RAW, không chứng minh RPC sẽ thành công hay phục dựng context nhiều record/HTTP/DB/log lịch sử. CLEAN thiếu được đánh dấu `UNDETERMINED_RAW_ONLY`. Các phiên bản RAW được kiểm tra riêng. CLI không in exception DB có thể chứa cấu hình.

Xem trạng thái issue đã persist bằng SQL riêng:

```sql
SELECT symbol,trading_date,status,severity,issue_count,
       details->>'decision' AS decision,details->>'raw_hash' AS raw_hash,
       details->'issues' AS issues,details->'preserved_fields' AS preserved_fields
FROM public.stock_data_quality_logs
WHERE check_name='stock_daily_validation_v1' AND timeframe='1d'
  AND status='ACTIVE' AND symbol='TCB'
  AND trading_date BETWEEN DATE '2026-03-05' AND DATE '2026-03-06';
SELECT symbol,trading_date,status,details->'history' AS history
FROM public.stock_data_quality_logs
WHERE check_name='stock_daily_validation_v1' AND symbol='TCB'
  AND trading_date BETWEEN DATE '2026-03-05' AND DATE '2026-03-06';
```

## Owner triển khai và rollback

Migration [`20261103_stock_daily_quality_v1.sql`](../migrations/20261103_stock_daily_quality_v1.sql) được viết theo quy ước date-prefix hiện tại; môi trường không có Supabase CLI. Owner tự apply, không chạy tự động trong ingest.

1. Pause writer Stock Daily theo lịch/thủ công, chờ run đang chạy kết thúc; review/backup theo quy trình owner.
2. Owner apply migration: thêm một cột text nullable với check NULL/VALID/PARTIAL, reuse/ensure unique index log hiện có, thêm RPC invoker giới hạn execute. Không rewrite status hoặc giá trị lịch sử, không thêm bảng. Lock timeout 5 giây. Nếu log trùng identity, migration fail rõ ràng, không tự deduplicate. Nếu index chưa có, việc tạo index có thể khóa bảng.
3. Chạy SQL catalog chỉ đọc dưới đây rồi deploy app tương ứng. Không trộn writer cũ/mới: upsert cũ không enforce merge/status V1. App mới chạy trước migration sẽ fail và có thể để lại RAW-only. Kiểm tra quyền service_role và visibility schema cache PostgREST trước khi mở write.
4. Chạy diagnostic đúng scope, review RAW/issue rồi owner mới chủ động backfill dưới đây. Sau đó kiểm tra CLEAN/status/issues/provenance.
5. Mở lại writer. Features chỉ chạy bằng quyết định riêng sau khi kiểm tra input. Code features không đổi và chưa tự lọc PARTIAL; downstream phải xử lý status/field nullable.

```sql
SELECT column_name,data_type,is_nullable FROM information_schema.columns
WHERE table_schema='public' AND table_name='stock_daily' AND column_name='validation_status';
SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid='public.stock_daily'::regclass AND conname='stock_daily_validation_status_v1_check';
SELECT indexname,indexdef FROM pg_indexes
WHERE schemaname='public' AND tablename IN ('stock_daily','stock_raw_daily','stock_data_quality_logs');
SELECT p.proname,p.prosecdef,p.proconfig,
 has_function_privilege('anon',p.oid,'EXECUTE') AS anon_execute,
 has_function_privilege('authenticated',p.oid,'EXECUTE') AS authenticated_execute,
 has_function_privilege('service_role',p.oid,'EXECUTE') AS service_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname='persist_stock_daily_validation_v1';
SELECT validation_status,count(*) FROM public.stock_daily GROUP BY 1;
SELECT symbol,trading_date,validation_status,foreign_remaining_room,source,updated_at
FROM public.stock_daily WHERE symbol='TCB'
 AND trading_date BETWEEN DATE '2026-03-05' AND DATE '2026-03-06';
```

RPC kỳ vọng `prosecdef=false`, anon/authenticated execute false, service_role true. Row lịch sử vẫn NULL sau migration. Runtime còn cần schema usage, SELECT/INSERT/UPDATE CLEAN/log, SELECT RAW và USAGE sequence log; catalog đã kiểm tra có các quyền này. Không mở rộng grant public.

Rollback: pause writer V1, chủ động deploy app trước, giữ cột nullable và quality evidence. App cũ bỏ qua metadata và không enforce V1. Chỉ bỏ RPC/check/cột trong schema rollback được review riêng sau khi gỡ code phụ thuộc; không xóa log/RAW hoặc rewrite giá trị thị trường. Migration không khôi phục giá trị từ ingest sau triển khai.

## Rerun đúng scope — WRITE, chỉ owner

Chỉ sau migration, app tương ứng và review diagnostic; task này chưa chạy lệnh:

```bash
python main.py stock-eod-backfill --from 05/03/2026 --to 06/03/2026 --symbols TCB --data-source ssi_v3
```

Lệnh gọi SSI và ghi RAW/CLEAN/issues; giữ quy tắc active symbol/ngày hợp lệ hiện có. Không tự mở rộng scope. Record RAW-only chỉ lỗi optional có thể vào CLEAN nếu core source hiện tại hợp lệ. Không sửa RAW cũ, không tự rerun features. Giữ `stock-eod`/`stock-eod-backfill`, date aliases và source options; không phục hồi alias đã bỏ. PARTIAL vẫn theo exit policy cũ, phải đọc JSON status thay vì chỉ shell exit.

Summary gồm `valid_clean_writes`, `partial_clean_writes`, `rejected_records`, `mapping_failures` (record có lỗi mapping, kể cả đã recover), `validation_issues` (số issue), `persistence_failures`. Stock backfill nay tổng hợp cả lỗi ingest trả về, tránh FAILED/zero error. EOD trả PARTIAL khi daily write PARTIAL dù completeness presence pass. CLI per-symbol không in payload đầy đủ.

## Kiểm chứng và giới hạn

Các lệnh offline đã chạy (đã activate virtualenv của repo):

```bash
source .venv/bin/activate
python -m pytest -q tests/validation/test_stock_daily_v1.py tests/validation/test_stock_daily_diagnostic.py tests/validation/test_stock_daily_v1_postgres.py tests/database/test_stock_daily_quality_rpc.py tests/ingest/test_daily_ingest_payload_reuse.py tests/data_sources/test_ssi_v3_stock_daily.py tests/pipeline/test_backfill_pipeline.py tests/pipeline/test_stock_eod_pipeline.py
python -m pytest -q
python -m compileall -q main.py src scripts tests
python main.py --help
python main.py stock-eod-quality --help
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
git diff --check
```

Baseline local: focused 70 passed/12 skipped; full 1.285 passed/22 skipped. Không còn test liên quan fail. Mười hai test SQL mới cần PostgreSQL local dùng một lần qua TEST_DATABASE_URL; local không có PostgreSQL/Docker daemon. CI hiện có PostgreSQL 16 để kiểm chứng transaction, migration replay, NULL lịch sử, idempotency/resolve, giữ field cũ, bảo vệ downgrade, quyền invoker và trigger bỏ qua write. Kết quả CI cuối ghi trong PR. Chưa kiểm chứng SSI live, chưa migration/backfill/write production. Catalog chỉ đọc không chứng minh ingest production sau deploy; owner phải chạy check đúng scope ở trên.

## Danh sách file

### Đã sửa

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_PIPELINE.md`
- `docs/README.md`
- `docs/README.vi.md`
- `docs/STOCK_EOD_PIPELINE.md`
- `docs/STOCK_EOD_PIPELINE.vi.md`
- `docs/backfill/README.md`
- `docs/backfill/README.vi.md`
- `migrations/README.md`
- `migrations/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/parser.py`
- `src/cli/stock.py`
- `src/contracts/engine.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/database/client.py`
- `src/ingest/maintenance/backfill.py`
- `src/ingest/stock_daily/README.md`
- `src/ingest/stock_daily/README.vi.md`
- `src/ingest/stock_daily/daily.py`
- `src/ingest/stock_daily/daily_mapper.py`
- `src/ingest/stock_daily/daily_service.py`
- `src/ingest/workflows/stock_eod.py`
- `src/providers/ssi/adapters/v3.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/validators/README.md`
- `src/quality/validators/README.vi.md`
- `tests/data_sources/test_ssi_v3_stock_daily.py`
- `tests/ingest/test_daily_ingest_payload_reuse.py`
- `tests/pipeline/test_backfill_pipeline.py`

### Tạo mới

- `docs/STOCK_DAILY_QUALITY_V1.md`
- `docs/STOCK_DAILY_QUALITY_V1.vi.md`
- `migrations/20261103_stock_daily_quality_v1.sql`
- `src/quality/stock_daily_diagnostics.py`
- `src/quality/validators/stock_daily_v1.py`
- `tests/database/test_stock_daily_quality_rpc.py`
- `tests/validation/test_stock_daily_diagnostic.py`
- `tests/validation/test_stock_daily_v1.py`
- `tests/validation/test_stock_daily_v1_postgres.py`

Không xóa file.
