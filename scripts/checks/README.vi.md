# checks — hướng dẫn công cụ

[English](README.md) · [CLI](../../docs/CLI_USAGE.vi.md)

Chạy tại root với venv Python 3.11 đã cài requirements. Ngày stock nhận DD/MM/YYYY hoặc ISO; riêng đối soát Phase 0 nhận ISO. Phân biệt kiểm tra parser với kết quả dữ liệu thật; các ví dụ chỉ kiểm tra offline. Script NOT_IMPLEMENTED giữ tham số để tương thích nhưng không gọi SSI/DB kể cả --write; help exit 0, gọi nghiệp vụ trả JSON FAILED/NOT_IMPLEMENTED exit 1.

## `scripts/checks/check_ingest.py`

Kiểm tra completeness daily/intraday đã lưu.

**READ-ONLY — database read**. Phụ thuộc: Supabase. Đầu ra: stdout chỉ chứa JSON; exit 0 OK, 1 PARTIAL/FAILED hoặc lỗi query, 2 input sai/kết quả không xác định. Progress đưa sang stderr.

```bash
python scripts/checks/check_ingest.py --date 19/10/2026 --symbols SSI
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--date` | required=True |
| `--symbols` | nargs='+', default=None |

## `scripts/checks/check_supabase.py`

Kiểm tra kết nối các bảng lõi.

**READ-ONLY — database read**. Phụ thuộc: SUPABASE_URL + SUPABASE_SERVICE_KEY. Đầu ra: Per-table PASS/FAIL; exit 0 pass, 1 failures, 2 missing config / thiếu cấu hình.

```bash
python scripts/checks/check_supabase.py
```

Không có tham số CLI; check_supabase không có help parser.

## `scripts/checks/check_ssi_ingest_schema.py`

Select cột bắt buộc và in SQL kiểm tra constraint.

**READ-ONLY — database read**. Phụ thuộc: Supabase. Đầu ra: Table/column PASS/FAIL; exit 1 failures, 0 otherwise / khi không lỗi.

```bash
python scripts/checks/check_ssi_ingest_schema.py
```

Không có tham số CLI; check_supabase không có help parser.

## `scripts/checks/phase0_validate_schema.py`

Kiểm tra catalog PostgreSQL bằng transaction chỉ đọc.

**READ-ONLY — database read**. Phụ thuộc: PHASE0_DATABASE_URL or --database-url. Đầu ra: JSON PASS/FAIL/UNKNOWN; exit 0/1/2.

```bash
python scripts/checks/phase0_validate_schema.py
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--database-url` | default=os.getenv('PHASE0_DATABASE_URL') |

## `scripts/checks/phase0_reconcile_sample.py`

Đối soát một mẫu raw/clean/feature có giới hạn.

**READ-ONLY — database read**. Phụ thuộc: Supabase. Đầu ra: Payload + reconciliation JSON; exit 1 FAIL, 2 UNKNOWN, 0 otherwise.

```bash
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m --timestamp 2026-10-21T02:15:00Z
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-19 --timeframe 15m --tolerance 0.000001
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | required=True |
| `--date` | required=True |
| `--timeframe` | required=True, choices=('1m', '1d', '15m', '60m') |
| `--timestamp` | Instant có timezone đúng ngày VN; candle 1m hoặc bucket feature 15m/60m, không lấy hàng gần nhất |
| `--tolerance` | type=float, default=1e-06 |

## `scripts/checks/check_complete_ssi_ingest.py`

Smoke test SSI nhiều dataset trước đây; tắt do thiếu master.

**NOT_IMPLEMENTED**. Phụ thuộc: None / không có. Đầu ra: FAILED + error_type NOT_IMPLEMENTED; exit 1.

```bash
python scripts/checks/check_complete_ssi_ingest.py --help
```

| Tham số / alias | Quy tắc parser (required/default/choices/nargs) |
| --- | --- |
| `--symbol` | default='SSI' |
| `--date` | default=None |
| `--index-code` | default='VNINDEX' |
| `--write` | action='store_true' |
| `--write-intraday` | action='store_true' |
| `--force` | action='store_true' |

## Diễn giải và giới hạn

check_ingest không sửa dữ liệu; không dùng một số nến cố định làm bằng chứng đủ phiên. check_supabase chỉ select một hàng mỗi bảng, không kiểm tra unique index. check_ssi_ingest_schema còn dùng một số cột index/foreign cũ trước contract 2.0; có thể FAIL dù schema hiện tại đúng. Không tạo cột cũ để làm check pass; cần sửa diagnostic trong task code riêng. Phase 0 có thể UNKNOWN khi thiếu schema/nguồn; không nâng thành PASS. --timestamp tùy chọn giới hạn đúng hàng feature intraday, tolerance mặc định 1e-6. --database-url mặc định lấy PHASE0_DATABASE_URL; không đưa URL thật vào log hoặc lịch sử lệnh.

check_complete_ssi_ingest giữ --symbol (SSI), --date, --index-code (VNINDEX), --write, --write-intraday, --force nhưng tất cả nghiệp vụ bị tắt; không dùng nó để chứng minh ingest v3 hoạt động. Không có credential nào cần cho stub.

## Contract diagnostic Phase 0 SSI v3 (23/10/2026)

Schema verifier đọc catalog cho `public.stock_raw_intraday.payload` (JSONB, nullable, không default), unique identity `(symbol,timeframe,time)` của `public.stock_features` và đúng chữ ký `replace_features_atomic(text,text,timestamptz,timestamptz,jsonb)`. Chấp nhận index unique full valid/ready do PK/constraint bảo trợ, không phụ thuộc tên/thứ tự key; không chấp nhận partial/expression/nonunique/invalid. Giữ kiểm tra SECURITY DEFINER, search_path rỗng, service_role EXECUTE và cấm anon/authenticated/PUBLIC EXECUTE. PUBLIC được kiểm qua ACL grantee 0, không phải tên role. Không gọi RPC, DDL hay sửa schema.

Reconciliation chỉ dùng dữ liệu persisted, không gọi SSI hoặc manual ingest. `1m` đối chiếu raw → clean canonical, **không** query/yêu cầu stock_features. `1d` giữ stock_raw_daily → stock_daily → stock_features(1d). `15m/60m` đối chiếu raw 1m → clean 1m trong bucket chọn, rồi observed clean → OHLCV/value của feature đã lưu bằng helper aggregation/closed-bucket thuần hiện có. Không tính indicator hoặc persist feature; cột feature khác ngoài phạm vi diagnostic.

Chỉ raw source `ssi_v3` được map bằng contract đã xác minh. Legacy `SSI`, nguồn không rõ, thiếu payload hoặc format không tương thích báo UNKNOWN, không diễn giải lại hay false PASS. `ohlc.tradingDate` dùng quy tắc nguồn local Việt Nam; offset UTC tương đương là cùng instant, giữ nguyên giây. Không làm tròn/dịch phút, không ước tính value hay đổi NULL thành 0. Volume/value so sánh số nguyên chính xác, không qua float/tolerance; OHLC dùng absolute/relative tolerance tường minh (mặc định 1e-6).

Mọi read reconciliation giới hạn đúng một mã/ngày Việt Nam theo UTC half-open. Có --timestamp: lấy đúng instant aware, không lấy hàng gần nhất. Không có timestamp: 1m chọn instant raw SSI v3 sớm nhất (hoặc raw sớm nhất nếu không có v3); xét tất cả phiên bản/source tại instant đó, nhiều candidate báo UNKNOWN. Thiếu raw chỉ chọn instant clean sớm nhất để báo thiếu lineage. Timeframe cao chọn bucket persisted mới nhất rồi xét raw/clean constituents; duplicate FAIL, source collision UNKNOWN. Không yêu cầu đủ 60 candle phát ra cho 60m; dùng grouping ngày/phiên VN, bucket label trái và session closure hiện có. Bucket mở/dở, input aggregate NULL hay thiếu evidence báo UNKNOWN; không đi vào helper fill value legacy. Aggregate observed bucket khớp không chứng minh coverage toàn nguồn.

Read trang 100 hàng kèm exact count; giới hạn mỗi ngày: intraday raw 3.000, clean 2.000, feature 200; daily raw/clean/feature 1.000/100/100. Cap/truncation/evidence thay đổi báo UNKNOWN. Giữ kết quả từng lớp và comparison. PASS là đối chiếu có evidence khớp; FAIL là mâu thuẫn xác minh được (ưu tiên hơn UNKNOWN lớp khác); UNKNOWN là thiếu/ambiguous/nguồn không hỗ trợ. Giữ WARNING. Exit reconciliation: 0 PASS/WARNING, 1 FAIL, 2 UNKNOWN. Summary có payload chỉ mang tính thông tin, không ghi đè kết quả lineage được chọn, nhất là 1m/daily.

Completeness vẫn gọi thuật toán check_ingest hiện có, không đổi threshold/ý nghĩa. OK chỉ chứng nhận structural check, không phải toàn SSI market coverage; gap có thể là no-trade, không dùng chuẩn universal 226. Exception được sanitize và exit khác 0; giữ JSON/status trả về gốc. Tất cả tool chỉ đọc, không migration, sửa dữ liệu/backfill, ingest, tính feature, signal/backtest. Không đổi guard manual pilot hoặc lệnh đang tắt.

Lệnh owner chỉ đọc (cấu hình credential local, không in secret):

```bash
python scripts/checks/phase0_validate_schema.py
python scripts/checks/check_ingest.py --date 21/10/2026 --symbols SSI
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 15m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 60m
```

Giữ JSON và scope chính xác. Scope persisted chưa có dữ liệu thì UNKNOWN là đúng; không ingest/sửa dữ liệu chỉ để ép diagnostic xanh. Xem [báo cáo xác minh theo ngày](../../docs/phase0/PHASE0_VALIDATION_REPORT.vi.md).
