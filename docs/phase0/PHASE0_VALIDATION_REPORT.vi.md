# Báo cáo kiểm chứng Phase 0

Phần đóng Phase 0 dưới đây là lịch sử. Báo cáo bảo trì/xác minh SSI v3 hiện tại ở mục 23/10/2026 phía dưới; Next step cũ là lịch sử, không phải yêu cầu mới.

**Quyết định: COMPLETE_WITH_NOTES**
**Ngày đóng:** 03/08/2026
**Phạm vi:** hạ tầng dữ liệu, validation dữ liệu và kiểm chứng feature deterministic; chưa triển khai Phase 1.

## Gate đóng Phase 0

| Gate | Kết quả | Evidence |
| --- | --- | --- |
| Schema production | `PASS_WITH_MANUAL_APPLY_NOTE` | `20260802_atomic_replace_features.sql` và `20260803_add_raw_intraday_payload.sql` đã được apply thủ công bằng Supabase SQL Editor. Kiểm tra production chỉ đọc xác nhận `stock_raw_intraday.payload jsonb` nullable/không default, RPC atomic có `SECURITY DEFINER`, `search_path` rỗng an toàn, đúng quyền role và unique index feature bắt buộc. Supabase CLI migration history có thể không có record; Phase 0 chấp nhận vì schema deployed đúng. Không rerun/repair migration chỉ để sửa history. |
| Lineage payload intraday mới | `PASS` | Chủ dự án đã kiểm tra row ingest intraday mới có `stock_raw_intraday.payload` khác NULL. Payload lịch sử NULL là đúng thiết kế và không cần backfill. |
| Sample SSI → raw → clean → feature | `PASS` | Chủ dự án chọn symbol/ngày/timeframe daily và intraday trên production, đối chiếu source, raw, clean và feature. Field khớp gồm identity/mapping payload cùng OHLCV/value; không còn mismatch critical chưa giải thích. Report chưa lưu exact identifier của sample, nên run sau phải lưu command output và scope. |
| Regression offline | `PASS` | Test deterministic cover pagination, mapping, completeness, parity feature, atomic replacement và hành vi validation Phase 0. |
| Calendar/completeness | `PASS_WITH_NOTES` | Completeness theo symbol, ngày Việt Nam, source, timeframe và session quan sát; report có count, first/last timestamp, duplicate và gap classification. Không dùng 226 candle làm chuẩn universal. |

## Validation chỉ đọc có thể chạy lại

```bash
PHASE0_DATABASE_URL='postgresql://...' python scripts/checks/phase0_validate_schema.py
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-08-03 --timeframe 15m --timestamp 2026-08-03T02:00:00Z
```

Command schema bắt buộc PostgreSQL `default_transaction_read_only=on`. Command reconcile chỉ SELECT có giới hạn. Kết quả là `PASS`, `FAIL` hoặc `UNKNOWN`; thiếu evidence không thành false pass. Payload check đọc tối đa 100 row, chấp nhận NULL lịch sử và trả `UNKNOWN` nếu không tìm thấy sample khác NULL. Tolerance số mặc định là `1e-6` cho absolute/relative.

## Giả định calendar và completeness

- Diễn giải session/ngày theo `Asia/Ho_Chi_Minh`, giữ timestamp UTC timezone-aware khi lưu.
- Ngày trong tuần không tự động là ngày giao dịch; cần phân biệt empty, holiday, halt, phiên rút ngắn và lỗi source khi evidence cho phép.
- Không dựng row ngày nghỉ, forward-fill candle hoặc đổi missing thành 0.
- Repo chưa có nguồn calendar/status sàn authoritative có version được duyệt. Trước khi có nguồn đó, ngày lễ trong tuần và phiên ngoại lệ có thể là `UNKNOWN`/warning thay vì false failure.
- Count candle thay đổi theo auction, thanh khoản, halt, phiên rút ngắn, convention timestamp và behavior SSI; 226 không phải expected count universal.

## Ảnh hưởng dữ liệu và migration

Closure này không apply migration, ghi production, ingest, gọi RPC replace, delete, rebuild feature hay backfill. `stock_raw_intraday.payload` lịch sử tiếp tục NULL nếu trước đây không capture. Không đổi formula feature nên không cần backfill feature.

## Rủi ro còn lại

1. Supabase CLI migration history có thể không phản ánh SQL apply thủ công; trước deployment sau phải kiểm tra schema deployed thay vì chỉ dựa history.
2. Evidence sau cần lưu exact symbol, ngày, timeframe, timestamp và output; owner validation dùng để đóng Phase 0 không cung cấp các identifier đó trong repo.
3. Chưa triển khai nguồn calendar/status phiên ngoại lệ authoritative, có version và được duyệt.
4. Live check SSI/Supabase cần credential ngoài; run offline phải báo `UNKNOWN`, không được nhận là live verification.

## Bước tiếp theo

Bắt đầu đặc tả Phase 1 cho quy tắc chiến lược dùng chung và backtest point-in-time.

## 23/10/2026 — Báo cáo bảo trì diagnostic SSI v3

**Trạng thái: COMPLETE cho code, regression offline và catalog live chỉ đọc. Đối soát lineage SSI v3 live còn chờ scope persisted có dữ liệu do owner chọn.** Đã kiểm tra lại dev `278da438138b50e6820b2888f17d52aa2927c96a` (PR #182). Không tạo subsystem quality, source integration hay lệnh CLI mới.

Lỗi ban đầu: verifier còn raw_intraday/features cũ, nhận diện unique qua tên/text index, coi PUBLIC như role thật trong has_function_privilege; thiếu 1m/mapper intraday; chọn evidence limit(1) tùy ý; aggregate thủ công đổi NULL thành 0; so BIGINT qua float; missing che mismatch; completeness luôn exit 0.

Sửa schema verifier: dùng stock_raw_intraday.payload JSONB/nullable/không default và metadata unique identity stock_features từ pg_index (valid/ready/unique/full/plain key). Chấp nhận index PK/constraint không phụ thuộc tên. Giữ đúng signature replace_features_atomic, SECURITY DEFINER, search_path rỗng, service_role EXECUTE và cấm anon/authenticated/PUBLIC; PUBLIC được kiểm qua ACL grantee 0, không phải role giả. Mỗi check giữ status/expected/observed/reason, read_only=true; không gọi RPC/auto repair.

Reconciliation nhận 1m/1d/15m/60m, SELECT đúng một mã/ngày Việt Nam, phân trang exact count và có bound. Giữ report field hiện có, thêm từng lớp/comparison/selection/diagnostic code. 1m dùng mapper SSI v3 thuần trên payload persisted, không query/yêu cầu feature. Timestamp so instant UTC aware và giữ giây; volume/value nguyên chính xác không float/tolerance/ước tính/zero fill; OHLC absolute/relative tolerance mặc định 1e-6. Thiếu source value giữ NULL: NULL/NULL có thể PASS về bảo toàn missing, NULL/zero là mâu thuẫn.

Chỉ source ssi_v3 được map; legacy SSI/unknown, NULL/payload không tương thích và collision raw báo UNKNOWN. --timestamp đúng instant, không lấy gần nhất. Mặc định 1m chọn raw v3 sớm nhất (hoặc raw sớm nhất nếu không có v3), kiểm tất cả candidate cùng instant. Timeframe cao chọn bucket feature persisted mới nhất, đối chiếu raw/clean constituents. Duplicate canonical FAIL; nhiều phiên bản/source raw UNKNOWN, không chọn tùy ý.

Daily giữ stock_raw_daily → stock_daily → stock_features(1d), mapper daily thật và không diễn giải legacy như v3. Clean → feature 15m/60m OHLCV/value dùng helper aggregation/closed-bucket thuần hiện có theo ngày/phiên VN và label trái; không tính indicator/persist feature, không ép số emitted candle. Bucket mở/dở hoặc input NULL báo UNKNOWN trước helper estimate legacy; giá clean sai và feature mismatch thật FAIL. Các lớp báo độc lập, FAIL xác minh được ưu tiên hơn UNKNOWN lớp khác. Coverage vẫn UNVERIFIED dù aggregate observed khớp.

Completeness tiếp tục gọi thuật toán check_ingest, giữ full JSON/status gốc. Exit 0=OK, 1=PARTIAL/FAILED hoặc lỗi query, 2=input sai/status không xác định. Progress chuyển stderr để stdout JSON parse được; lỗi sanitize, có type/status và nonzero. Không đổi threshold/nghĩa coverage. Reconciliation exit 0 PASS/WARNING, 1 FAIL, 2 UNKNOWN; payload-presence chỉ là thông tin, không gate daily/lineage được chọn. Không đổi guard/readiness manual pilot hoặc bật ingest/backfill/streaming đang tắt.

### Xác minh và giới hạn

```bash
.venv/bin/python -m pytest -q tests/validation/test_phase0.py
.venv/bin/python -m pytest -q tests/validation/test_intraday_validator.py
.venv/bin/python -m pytest -q tests/ingest/test_ingest_check.py
.venv/bin/python -m pytest -q tests/ingest/test_manual_intraday.py
.venv/bin/python -m pytest -q tests/cli/test_phase0_checks.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python scripts/checks/phase0_validate_schema.py --help
.venv/bin/python scripts/checks/phase0_reconcile_sample.py --help
.venv/bin/python scripts/checks/check_ingest.py --help
git diff --check
```

Baseline targeted: 105 passed. Suite riêng cuối: Phase 0 **78 passed**, intraday validator **30 passed**, ingest completeness **15 passed**, manual pilot **54 passed**, CLI diagnostic **40 passed**. Full suite cuối **903 passed, 7 skipped**; compile/help/diff sạch. Full run trước mười edge case cuối: 893/7. Test offline cover catalog canonical, unique/RPC security sai, BIGINT và chênh một đơn vị, provenance/ambiguity, exact instant/giây, paging/bound, NULL/zero, daily, 15m/60m/nghỉ trưa/ngày/bucket, bucket dở, mismatch, read-only guard và CLI JSON/status. Fixture synthetic chỉ dành test, không gán là live SSI capture.

Qua kết nối Supabase TradingTPus_DS, chỉ chạy SELECT: đúng ba query catalog trích từ verify_schema xác nhận payload JSONB nullable/không default, RPC security đúng và hai unique hợp lệ stock_features_pkey/stock_features_symbol_timeframe_time_key; index thường nonunique bị loại đúng. Đưa kết quả catalog live vào verifier trả PASS. Không thực thi RPC replace. SQL probe raw/clean có limit cho SSI ngày Việt Nam 2026-10-21 (UTC [2026-10-20T17:00Z,2026-10-21T17:00Z)) không có raw; SELECT đếm source đúng scope cũng không có hàng. Không nhận lineage live PASS cho scope rỗng và không ingest để đổi kết quả.

Bảy test integration replacement RPC PostgreSQL cần TEST_DATABASE_URL nên skip; không có binary PostgreSQL/disposable DB khả dụng. CLI end-to-end local chưa có credential DB; tách rõ xác minh SELECT catalog qua connector và chạy CLI native. Không gọi live SSI API. Đã xem docs/changelog Supabase hiện tại; markdown không hỗ trợ nên xem HTML. Quy trình owner chỉ đọc ở [runbook checks](../../scripts/checks/README.vi.md).

### Tác động DB, UNKNOWN còn lại và task tiếp

Migration: **none**. Thay schema/constraint/RPC: **none**. Dữ liệu DB bị tác động: **none** (chỉ SELECT). Backfill: **không cần/none**. Không ingest, tính feature, signal/backtest/alert; không đổi formula/output persisted.

**No live database writes were executed.**

UNKNOWN còn lại: thiếu raw/clean/feature, legacy/unknown source, payload NULL/không tương thích, nhiều raw version/source, bucket mở/dở, input aggregate NULL, read cap/bound/evidence thay đổi hoặc không truy vấn được. Clean→feature equality chỉ so OHLCV/value từ observed clean, không chứng nhận indicator hoặc completeness nguồn/phiên chính thức. Không sửa/diễn giải lại timestamp hay provenance value lịch sử. Writer khác có thể đổi evidence sau SELECT; lưu scope/output và ưu tiên thời điểm không có writer.

Lệnh owner chỉ đọc:

```bash
python scripts/checks/phase0_validate_schema.py
python scripts/checks/check_ingest.py --date 21/10/2026 --symbols SSI
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1d
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 1m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 15m
python scripts/checks/phase0_reconcile_sample.py --symbol SSI --date 2026-10-21 --timeframe 60m
```

Dùng scope có dữ liệu persisted để thu evidence lineage; scope rỗng phải UNKNOWN. Bước tiếp theo: owner xác minh diagnostic, lưu JSON/timestamp chính xác. Chỉ task riêng được ủy quyền sau đó mới đánh giá incremental/backfill intraday. Không đổi strategy, công thức feature, signal/backtest/alert.

### File sửa

- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/DATA_CONVENTIONS.vi.md`
- `docs/phase0/PHASE0_VALIDATION_REPORT.md`
- `docs/phase0/PHASE0_VALIDATION_REPORT.vi.md`
- `scripts/checks/README.md`
- `scripts/checks/README.vi.md`
- `scripts/checks/check_ingest.py`
- `scripts/checks/phase0_reconcile_sample.py`
- `src/quality/README.md`
- `src/quality/README.vi.md`
- `src/quality/validators/README.md`
- `src/quality/validators/README.vi.md`
- `src/quality/validators/phase0.py`
- `tests/validation/test_phase0.py`

### File tạo

- `tests/cli/test_phase0_checks.py`
