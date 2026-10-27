# Đồng bộ master SSI v3 có guard — symbols và securities

[English](README.md)

Tái sử dụng kiến trúc versioned từ PR #186. **symbols** và **securities** của SSI v3
READY cho hợp đồng refresh không xóa có guard dưới đây. **index_master** và
**index_components** giữ nguyên BLOCKED. READY xác nhận mapper, kiểm tra ba board
và persistence có guard; không chứng nhận universe toàn thị trường authoritative.

## Nguồn, phạm vi và completeness

[Bằng chứng owner 26–27/10/2026](../../../docs/SSI_V3_MASTER_EVIDENCE.vi.md):
GET /api/v3/data/securitiesByBoard?board=HOSE/HNX/UPCOM trả JSON array không phân
trang, count quan sát 793/410/851, tổng 2.054. Đây là mốc lịch sử phát hiện bất thường,
không phải tổng cố định phải khớp hay bằng chứng toàn thị trường.

Mỗi lần chạy gọi riêng từng board qua SSIV3Client, yêu cầu HTTP 200 và parse trọn
body byte thành array. Kiểm tra mọi identity/board/kiểu/optional numeric/date; chặn
đúp trong và giữa board. Không thêm paging parameter giả. Cả ba board phải thành
công; không bỏ row lỗi rồi báo snapshot hoàn chỉnh. Hai dataset dùng chung fetch/
mapper; CLI độc lập lấy snapshot độc lập, không cache nguồn toàn cục.

Report tách parse body HTTP, enumerate ba board, consistency nội bộ và coverage
thị trường. pagination_complete nghĩa là nhận/kiểm tra đủ scope response ba board,
không phải tổng thị trường. mode=UNPAGINATED_ARRAY, provider_reported_total=null,
authoritative_market_completeness=UNVERIFIED luôn hiển thị. HTTP 200, array parse
được hay ngưỡng count không chứng minh SSI đã trả tất cả chứng khoán.

Policy bảo thủ, chạy trước mutation và trước SOURCE_MISSING:

- Board rỗng, HTTP/body lỗi/cắt, board sai, row invalid/đúp, board thất bại, vượt giới
  hạn row/body hoặc lỗi nguồn đều chặn cả dataset, không ghi một phần snapshot.
- Count board thấp hơn 50% mốc owner gây SOURCE_COUNT_REGRESSION. Không yêu cầu count
  bằng mốc cũ; tăng/giảm bình thường vẫn được. Chỉ cập nhật mốc sau điều tra nguồn
  riêng, không bypass CLI. Đây là anomaly policy, không phải ước tính tổng thị trường.
- Universe hoặc nhóm market có sẵn trong DB giảm dưới 50% gây SOURCE_DB_COUNT_REGRESSION
  trước khi kết luận hàng loạt missing. Report có count/delta board, tổng và phân bố
  sec_type nguồn so với DB securities khi có. Owner chưa cung cấp phân bố type lịch
  sử. Type lạ được giữ và đếm, không ép về Stock hoặc lọc bỏ.
- Lỗi board sau vẫn giữ diagnostics board trước; không write subset. Ngay khi mọi
  guard đạt, authoritative completeness vẫn UNVERIFIED. Tránh sync writer chạy chồng.

Giới hạn: ba board data request, mặc định tối đa ba attempt mỗi request (client
hard cap năm), auth dùng chung, timeout 30 giây/request, body parse tối đa 16 MiB và
20.000 records/board. 429/5xx bounded backoff; Retry-After đến 30 giây được tôn trọng,
lâu hơn hoặc sai thì dừng thay vì retry sớm. Mã lỗi riêng cho auth/HTTP/rate limit,
transport cắt, JSON malformed/non-finite/duplicate key. Không log credential/token,
auth payload hay full error body. Agent không gọi SSI live trong task này.

## Mapping canonical

| SSI | symbols | securities |
| --- | --- | --- |
| symbol | symbol | symbol |
| board | market | market, exchange |
| symbolNameVi | name | stock_name |
| symbolNameEn | — | stock_en_name |
| stockType | — | sec_type |
| lotSize | — | lot_size |
| listedShare | — | listed_share |
| firstTradingDate | — | first_trading_date |
| lastTradingDate | — | last_trading_date |
| maturityDate | — | maturity_date |
| source object đã sanitize | — | raw |

Symbol trim/uppercase, hỗ trợ bond identifier dài trong contract tối đa 64 ký tự.
Board phải đúng HOSE/HNX/UPCOM và khớp request. Tên giữ Unicode; optional thiếu/null/
chuỗi trống thành NULL. Numeric/date không rỗng nhưng sai chặn cả hai dataset.
Numeric string và JSON number parse chính xác không qua binary float; ngày
YYYY/MM/DD hoặc YYYY-MM-DD thành ISO. Không zero/name/issuer/type fallback; zero
vẫn zero. Stock/Bond/ETF Product/Investment Fund/type lạ/NULL đều được biểu diễn;
tồn tại trên thị trường không có nghĩa đủ điều kiện chiến lược T+.

raw là bản sao JSON-compatible đã sanitize đệ quy: bỏ key secret và redaction giá
trị credential cấu hình; field nguồn lạ chỉ giữ raw nếu JSON-safe. Decimal JSON
tích phân thành integer, còn lại thành decimal string để tương thích SDK/JSONB.
Không tạo cột mới từ field lạ. issuer, issue_date, tick fields không có nguồn mapping,
report unsupported và giữ giá trị DB có sẵn. Cột numeric securities được select/cast text khi compare, nhận ack và readback để tránh SDK decode binary float; client DB/giá chung không đổi. Mapping version:
ssi_v3.securitiesByBoard.1.0.0. Inspector symbol_list đã map stock_name/market/
exchange/security_type; PASS chỉ kiểm tra row mapping, không chứng minh toàn board/
universe hay khả năng ghi.

## CLI và điều kiện DB

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --dry-run
python main.py sync-master-data --dataset securities --data-source ssi_v3 --dry-run
python main.py init --dataset symbols --data-source ssi_v3 --dry-run
```

Cần SSI_API_KEY/SSI_API_SECRET và Supabase service credential cục bộ để fetch/compare.
Dry-run không mutation. Bỏ source chọn provider master verified READY mới nhất cho
dataset, hiện là ssi_v3 cho hai dataset này. ssi_v2/v4/v5/auto bị từ chối, không
fallback. Price registry và daily/intraday không thay đổi.

Chỉ sau khi xem cả hai dry-run, owner có thể chạy:

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --write
python main.py sync-master-data --dataset securities --data-source ssi_v3 --write
```

--write cần đúng một --dataset tường minh. all+write và command-only write trả exit 2;
--dry-run/--write loại trừ nhau. all hoặc bỏ dataset chỉ preview, hiện PARTIAL vì index
BLOCKED. Chỉ OK trả exit 0; PARTIAL/FAILED/BLOCKED/UNSUPPORTED trả exit 1.

Catalog TradingTPus_DS kiểm tra chỉ đọc ngày 27/10/2026 xác nhận primary key symbol
của hai bảng, kiểu numeric/date/JSONB, status check và **không có FK securities→symbols**.
Securities chạy độc lập; symbols-first chỉ là khuyến nghị vận hành, không dependency
ẩn, không tự tạo hàng liên quan ngoài dataset. Recheck nếu schema triển khai thay đổi.

## Persistence, operator và recovery

CLI → registry hiện có → adapter v3 → MasterSnapshot → canonical validation → compare
hiện có → MasterStore guard → readback → JSON. Không tạo CLI/orchestrator cạnh tranh;
generic SupabaseClient.upsert_symbols/upsert_securities giữ nguyên.

DB read trang 100 theo thứ tự khóa, exact count ổn định, identity unique, tối đa
100.000 rows. Validate toàn bộ nguồn/retention/plan trước mutation đầu tiên.
Chỉ NEW/CHANGED ghi; UNCHANGED bỏ qua; SOURCE_MISSING không xác nhận delisting, không
xóa hoặc inactive, không thay membership. Không NULL đè descriptive đã biết.
Existing symbols giữ status/intraday_status; insert inactive/inactive. SSI status/type
không bật eligibility. Hành vi index/status hiện có không đổi.

Insert theo unique key ignore_duplicates; concurrent insert không ghi đè controls.
Update compare-and-set descriptive, không gửi status. Timestamp từ ứng dụng. Kiểm
tra acknowledgement và readback; actual count là số ack, khác planned.
**Transaction theo row/request, không atomic toàn dataset/nhiều bảng.** Lỗi dở dang/
mơ hồ dừng, giữ bằng chứng đã ack và PARTIAL/nonzero; insert_counts_confirmed=false
bao gồm update chưa rõ kết quả. Không retry DB mơ hồ, rollback/delete/cleanup tự động.
Kiểm tra identity chỉ đọc, chạy lại DRY_RUN, owner quyết định write đúng dataset;
row đã đúng trở thành UNCHANGED. DB read nhiều trang không repeatable-read; nên một
sync writer, đồng thời vẫn bảo toàn thay đổi flag từ operator.

## SQL chỉ đọc cho owner

```sql
select status,intraday_status,count(*) from public.symbols group by 1,2;
select market,count(*) from public.symbols group by 1 order by 1;
select market,sec_type,count(*) from public.securities group by 1,2 order by 1,2;
select * from public.symbols where symbol='SSI';
select * from public.securities where symbol='SSI';
select conrelid::regclass,conname,pg_get_constraintdef(oid)
from pg_constraint where conrelid in ('public.symbols'::regclass,'public.securities'::regclass);
```

SQL dữ liệu cho owner chưa được thực thi; agent chỉ query catalog và kiểm tra cast numeric literal. Không hàng
production nào được ghi. Không migration, đổi schema, backfill giá, feature/signal/
backtest, workflow hoặc schedule.

## Thêm version và trạng thái xác minh

V4/v5 cần bằng chứng thật, adapter/mapper riêng và đăng ký capability tường minh.
Canonical validation, store, bảng và CLI vẫn tái sử dụng. retention_policy của
MasterSnapshot là metadata so sánh trung lập version, không đưa field SSI vào
orchestrator. Không tạo hỗ trợ v4/v5 hay index giả.

Audit dev d2211cb329dc0503661e43f11e7e7bd83cfc91a3 (PR #186 đã merge). Đã đọc
AGENTS/main/CLI/master modules/client/registry, schema/migration master, catalog
thật/constraints, inspector/mapping, test/fixture/workflow và docs hai ngôn ngữ.
Thiếu chính: stub adapter và descriptive inspector chưa map; không cần xây lại
kiến trúc. Schema đủ dùng. Danh sách file/lệnh/kết quả cuối ghi dưới.

Code hoàn thiện cho guarded symbols/securities. Giới hạn còn lại: không total
provider authoritative; không có full response archive owner; không live SSI smoke
của agent do thiếu credential; không kiểm chứng production write. Fixture dùng giá
trị minh họa theo contract field owner xác minh, không phải row live nguyên văn.
Test HTTP/SDK offline xác minh code, không phải quan sát live mới. Bước tiếp: owner
chạy hai dry-run, xem count/type distribution/NULL/unsupported/plan/control rồi mới
thực hiện write tường minh từng dataset.

## Báo cáo cuối — 27/10/2026

Trạng thái: **PARTIAL** cho xác minh tổng thể; code yêu cầu và kiểm thử offline đã hoàn tất. Agent SSI live smoke và kiểm chứng production write/readback NOT_RUN (không có credential SSI; cấm ghi production trong task). Tách bằng chứng nguồn owner xác minh khỏi mẫu offline minh họa. READY chỉ cho refresh có guard đã mô tả, market completeness authoritative UNVERIFIED. Hai capability index giữ BLOCKED.

Mục tiêu: **2 + 66 + 132 = 200 passed**. Toàn bộ: **1222 passed, 7 skipped** (31,65 giây); test PostgreSQL integration có sẵn cần TEST_DATABASE_URL. Compile/help/diff check đạt. Truy vấn SDK và numeric text cast kiểm thử HTTP offline; PostgreSQL query numeric literal chỉ đọc trả đúng decimal/integer lớn. Không write Supabase, không SSI request live.

Chỉ symbols/securities là đích ghi owner tương lai; task không ghi dữ liệu production. Giữ records/control có sẵn, row mới inactive, không migration/schema/backfill/schedule/downstream. Không xóa file; giữ wrapper tương thích. Bước tiếp: owner xem hai dry-run rồi write tường minh từng dataset.

```bash
.venv/bin/python -m pytest -q tests/ingest/test_master_data_pipeline.py
.venv/bin/python -m pytest -q tests/ingest/test_versioned_master_sync.py
.venv/bin/python -m pytest -q tests/ingest/test_ssi_v3_master_adapter.py tests/inspectors/test_ssi_api_mapping.py tests/data_preview/test_v3_client.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall main.py src scripts tests
.venv/bin/python main.py sync-master-data --help
.venv/bin/python main.py init --help
git diff --check
```

File sửa:

- `README.md`
- `README.vi.md`
- `docs/CLI_REFERENCE.md`
- `docs/CLI_REFERENCE.vi.md`
- `docs/CLI_USAGE.md`
- `docs/CLI_USAGE.vi.md`
- `docs/CURRENT_STATE.md`
- `scripts/inspectors/ssi_rest/README.md`
- `scripts/inspectors/ssi_rest/README.vi.md`
- `src/README.md`
- `src/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/contracts/README.md`
- `src/contracts/README.vi.md`
- `src/contracts/mappings/ssi_v3.json`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/master/contracts.py`
- `src/ingest/master/store.py`
- `src/ingest/master/sync.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/README.md`
- `src/providers/ssi/adapters/README.vi.md`
- `src/providers/ssi/adapters/master_v3.py`
- `src/providers/ssi/clients/rest_v3.py`
- `src/providers/ssi/master_contract.py`
- `src/providers/ssi/master_registry.py`
- `tests/ingest/test_master_data_pipeline.py`
- `tests/ingest/test_versioned_master_sync.py`

File tạo:

- `docs/SSI_V3_MASTER_EVIDENCE.md`
- `docs/SSI_V3_MASTER_EVIDENCE.vi.md`
- `tests/fixtures/data_preview/ssi_v3_master_contract_samples.json`
- `tests/ingest/test_ssi_v3_master_adapter.py`

File xóa: KHÔNG.
