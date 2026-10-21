# Báo cáo SSI v3 Stock Intraday 1m Preview

[English](SSI_V3_INTRADAY_PREVIEW_REPORT.md) · [Runbook và checklist](STOCK_INTRADAY_PIPELINE.vi.md)

## Kết quả: PARTIAL

Đã triển khai preview chỉ đọc, phân trang có giới hạn và mapper/validation dùng chung. Offline implementation đã được kiểm tra; xác minh SSI v3 live: **NOT_RUN** vì SSI_API_KEY và SSI_API_SECRET đều chưa cấu hình. Môi trường cũng chưa có quyền mạng SSI được xác minh. Không có response intraday v3 capture thật hoặc đặc tả SSI intraday mới để chốt query/đơn vị/bar convention. Không bịa fixture thị trường để thay bằng chứng. Test mới dùng đầu vào tổng hợp ghi rõ là synthetic, không phải response SSI.

Base dev được GitHub xác nhận: `804de03b819dedebcf32b1a97496d059978e1a63` (PR #179). Tree trùng snapshot tài liệu đã có; commit được kiểm tra hash trước khi tạo nhánh `feat/ssi-v3-intraday-preview`. Đã audit AGENTS, entrypoint/CLI/preflight, provider/contract/client/adapter, ingest helper, validator/completeness, estimator, DB client/schema/migration, inspector/test/workflow/tài liệu trước sửa. Không dùng API cũ hay adapter fallback.

## Hành vi cũ, khoảng trống và giải pháp

Client ohlc_1m trước chỉ nối ngày với giờ, dùng pager chung dừng khi trang ngắn. Inspector chỉ map một trang và tính value bằng vòng map thứ hai; timestamp naive bị mặc định thành giờ Việt Nam dù chưa có evidence v3. Contract nullable OHLCV không thay thế validation required OHLCV của pipeline. Metadata bar v2 không thể chứng minh bar v3.

Đã thêm builder 1m chuẩn hóa ngày/paging, tải đủ đến termination có bằng chứng hoặc lỗi rõ ràng, giữ raw/trang đã nhận và báo cắt cụt/lặp/tổng sai. Mapper dùng chung cho adapter/inspector, tái dùng estimator/validator. Timestamp thiếu timezone/ngày không được suy diễn. `--limit` chỉ in mẫu; `--full-json` cung cấp mọi trang đã tải. Production registry, CLI disable list và workflow không sửa.

## Endpoint, envelope, timestamp, đơn vị

Ứng viên duy nhất: GET `https://api.ssi.com.vn/api/v3/data/ohlc`, query symbol/from/to/timeFrame=1m/pageIndex/pageSize, optional ascending ở native route. Builder dùng cận ngày `YYYY/MM/DD 00:00:00` đến `YYYY/MM/DD 23:59:59`; tính bao gồm/sort/provider acceptance chưa được xác minh live. Inspector mặc định pageSize 10, max-pages 100; client pageSize 1000. Có kiểm tra syntax/range/paging trước I/O.

Decoder chỉ nhận các array/envelope từ convention sẵn trong repo, không coi đó là cấu trúc SSI thật đã xác minh. Nhận array top-level hoặc data/items/dataList/result, lồng giới hạn data/result/response; shape sai và provider failure là lỗi. Metadata pageIndex/pagesCount/totalRecord được kiểm tra khi có, không coi itemsCount là tổng mọi trang. Raw response envelope/candle giữ nguyên, không dùng source value làm turnover chuẩn.

Chỉ nhận time đầy đủ có offset/Z, chuẩn hóa UTC và kiểm tra phạm vi ngày Việt Nam. Từ chối time-only, date-only, naive, epoch và dạng khác chưa được xác minh; không ghép ngày request. Source date nếu có phải khớp timestamp. Giữ nguyên giây/phần lẻ. Timezone của timestamp naive, bar-start/bar-end, scale giá và per-candle volume: **BLOCKED** đến khi có nguồn thật. Không đổi definitions.json vì metadata v2 chỉ là lịch sử, chưa có bằng chứng thay bằng quy ước v3 nào.

## Mapping từng field

| Chuẩn | Xử lý |
| --- | --- |
| symbol | Request identity, đối chiếu source symbol nếu có |
| time | ohlc.time → intraday_timestamp, cần full aware timestamp |
| timeframe | 1m; từ chối timeFrame nguồn mâu thuẫn |
| open/high/low/close | Field cùng tên, float hữu hạn/dương, kiểm tra OHLC; chưa xác minh scale VND |
| volume | Số nguyên chính xác không âm/BIGINT từ field cùng tên; chưa xác minh đơn vị/per-candle; không lấy hiệu cumulative |
| value | Tái dùng int(round(close * volume)), ước tính; không đọc source value để persist |
| reference_price/ceiling_price/floor_price | NULL, unsupported vì chưa xác minh field/context; không đọc daily DB |

Optional thiếu vẫn null trong mapping evidence; thiếu OHLCV bắt buộc của record validation sẽ từ chối candidate. Raw và lý do lỗi vẫn giữ. Không sửa giá/volume/time lỗi thành hàng hợp lệ.

Ví dụ test synthetic mở rộng input 10.5/100 đã có trong repository (không phải SSI payload thật): `time=2026-09-08T09:15:00+07:00`, OHLC=10.5, volume=100 → `time=2026-09-08T02:15:00Z`, timeframe=1m, OHLC=10.5, volume=100, value=1050, ba giá context=null. `time=2026/09/08 09:15:00` không có timezone bị từ chối thay vì đoán.

## Bằng chứng pagination và chất lượng

Test kiểm tra hai trang ngắn nhưng không rỗng rồi một trang rỗng: cả ba lần gọi được thực hiện, không dừng sớm. Metadata terminal đúng kết thúc được; trang lặp/đảo lại hàng, pageIndex lệch, tổng thay đổi, total sai khi kết thúc, rỗng sớm và max-pages đều FAILED kèm raw đã nhận. Lỗi request sau trang đầu giữ raw/candidate trang đầu. Retry giới hạn và lỗi provider/JSON/auth/network được phân biệt với no-data. Request từ page>1 được ghi suffix scope.

Có kiểm tra identity/date/UTC, timestamp sai, finite OHLC/dương/bất đẳng thức, integer volume không âm, null, giá context thiếu, raw order, duplicate, giờ sáng/trưa/chiều/auction, gap liên tục và không nối qua ngày/nghỉ trưa. Không tạo nến hay số count cố định. Duplicate vẫn có trong bằng chứng, làm validation FAILED; structural warning riêng; completeness luôn UNVERIFIED, kể cả HTTP/paging/validation pass. Nonempty sạch vẫn chỉ PROVISIONAL, không phải nguồn đã chứng nhận.

## Contract lưu trữ — chỉ đọc code/schema

Schema hiện có raw stock_raw_intraday (symbol,time,data_hash unique, payload JSONB nullable, source mặc định SSI), clean stock_intraday (symbol,timeframe,time primary key; phân vùng tháng theo time). Migration 20260803 thêm payload trên raw_intraday; 20260826 đổi tên thành stock_raw_intraday. Đây là lịch sử đổi tên đã quan sát, chưa chứng minh schema production đã apply. Không sửa schema, conflict key hay lịch sử nguồn. Trước ingest tương lai cần kiểm tra constraint/partition/source/hash đúng triển khai và đề xuất riêng nếu thật sự cần thay đổi provenance key.

Migration: **none**. Database impact: **none** (không đọc/ghi DB, đổi hàng/bảng/index/partition). Backfill: **none**. Không thay feature/research/master/streaming; không bật lịch hay ingest production.

## Tệp sửa

- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/DATA_CONVENTIONS.vi.md`
- `docs/STOCK_INTRADAY_PIPELINE.md`
- `docs/STOCK_INTRADAY_PIPELINE.vi.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `scripts/inspectors/ssi_rest/endpoints.py`
- `scripts/inspectors/ssi_rest/inspect.py`
- `scripts/inspectors/ssi_rest/mapping.py`
- `src/contracts/mappings/ssi_v3.json`
- `src/contracts/transforms.py`
- `src/ingest/stock_intraday/README.md`
- `src/ingest/stock_intraday/README.vi.md`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/v3.py`
- `src/providers/ssi/clients/rest_v3.py`
- `tests/inspectors/test_ssi_api_mapping.py`

## Tệp mới

- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.md`
- `docs/SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md`
- `src/contracts/intraday_preview.py`
- `src/providers/ssi/adapters/intraday_preview.py`
- `tests/data_preview/test_intraday_preview.py`

## Lệnh kiểm tra và kết quả

```bash
.venv/bin/python -m pytest -q tests/inspectors tests/data_contracts tests/data_sources tests/data_preview tests/ingest tests/validation tests/cli
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python scripts/inspectors/ssi_rest/inspect.py list
.venv/bin/python scripts/inspectors/ssi_rest/inspect.py run --help
git diff --check
```

Test tổng hợp cuối: **372 passed**; full suite: **651 passed, 7 skipped** (PostgreSQL atomic replace cần TEST_DATABASE_URL). Có 74 test mới; một test cũ được sửa để từ chối giả định timezone naive. Test Daily/Index, feature và production capability guard vẫn pass; không sửa test feature. Compile/help/list/whitespace và link/cú pháp ví dụ tài liệu đã kiểm tra offline. Một lần gọi preview không có credential xác nhận FAILED/exit 1 và thông báo thiếu credential, không có traceback hay truy cập mạng. Không gọi SSI/Supabase live; không thực hiện write smoke test.

## Quyết định readiness và bước tiếp theo

**Không cho phép promotion production.** Nguy cơ còn lại: chưa có bằng chứng nguồn thật, đơn vị/time/bar convention/sort/cận và semantics metadata chưa rõ; coverage phiên và schema production chưa được chứng nhận. Bước kế tiếp là cấu hình credential và quyền truy cập SSI, chạy chỉ đọc SSI trên một ngày hoàn tất rồi thêm mã/ngày thứ hai, review raw/clean và chốt ngữ nghĩa. Sau chủ sở hữu chấp nhận, tạo task riêng để triển khai manual raw-first/validated-clean persistence, kiểm tra idempotency/partition/provenance, rồi mới thay registry/CLI; schedule/backfill vẫn là phạm vi riêng. Checklist đầy đủ trong runbook.

Kiểm tra cuối sau chỉnh giữ error body: `.venv/bin/python -m pytest -q tests/data_preview tests/data_sources tests/inspectors tests/cli` → **217 passed**. Kiểm tra link và request-plan/parser offline: **22 ví dụ inspector pass**. Full suite trước tinh chỉnh diagnostic này: 651 passed, 7 skipped; không thay thuật toán nguồn/feature.
