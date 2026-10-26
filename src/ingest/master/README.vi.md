# Đồng bộ master có guard và registry theo version

[English](README.md)

**Trạng thái triển khai: PARTIAL; xác minh nguồn production: BLOCKED.**
`sync-master-data` và alias `init` chạy orchestrator mới. Cả bốn capability master
SSI v3 hiện BLOCKED vì chưa có fixture response master thật và credential SSI.
Bản này chưa khởi tạo được master production. Không tự nâng provider thành READY.

## Bằng chứng SSI v3

Audit dev `32f03abab80648f15afa80cfeb31ea15027bd44d`, ngày 26/10/2026.
Inspector chỉ cung cấp định nghĩa request ứng viên:

| Dataset | Endpoint ứng viên | Contract request hiện có | Chưa xác minh |
| --- | --- | --- | --- |
| symbols | /api/v3/data/securitiesByBoard; /api/v3/data/masterdata | securitiesByBoard chọn đúng một symbol/board/index; masterdata from/to, pageIndex/pageSize | Tên trường identity/name, board, loại chứng khoán, HOSE/HNX/UPCoM và universe đầy đủ |
| securities | cùng hai endpoint trên | cùng request trên | Toàn bộ trường chi tiết, kiểu và ý nghĩa missing |
| index_master | /api/v3/data/indexList | board tùy chọn; inspector một trang | Mã/tên/sàn chỉ số, listing đầy đủ |
| index_components | /api/v3/data/securitiesByBoard | selector index là ứng viên | Quan hệ constituent và snapshot membership đầy đủ |

**Chưa có trường/mapping master v3 nào được xác minh trong bản này.** Alias của
inspector không chứng minh schema hay membership. Fixture securitiesSummary/OHLC
chỉ xác minh hợp đồng giá riêng của chúng. Không tạo fixture SSI master thành
công giả. Adapter v3 hiện báo lỗi an toàn khi gọi fetch/map và không tạo client.
SSIV3Client.paged() tổng quát chưa đủ chứng minh completeness master; không dùng
nó để nhận một response bị cắt thành universe đầy đủ. Auth/retry dùng client chung
khi có triển khai nguồn được xác minh sau này; không nhân đôi authentication.

## CLI

```bash
python main.py sync-master-data
python main.py init --dataset symbols --data-source ssi_v3 --dry-run
python main.py sync-master-data --dataset index_master --data-source ssi_v3 --dry-run
python main.py sync-master-data --help
python main.py init --help
```

Hiện trả exit 1/BLOCKED, không gọi API/DB. Bỏ dataset preview riêng cả bốn dataset.
Bỏ source chỉ chọn provider master đã đăng ký, verified và READY mới nhất cho
mỗi dataset; hiện không có, report NO_READY_MASTER_PROVIDER và danh sách capability
bị chặn. Chỉ định ssi_v3 trả MASTER_CAPABILITY_NOT_READY. ssi_v2/v4/v5/auto bị từ
chối exit 2; không fallback. Không thêm selector board/symbol/index chưa xác minh.

Cú pháp ghi cho owner sau khi nguồn được xác minh, **hiện vẫn BLOCKED**:

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --write
```

Mặc định DRY_RUN. --dry-run và --write loại trừ nhau; --write bắt buộc đúng một
dataset tường minh. Command-only write và all+write bị từ chối exit 2. all chỉ
preview. Dataset: symbols, securities, index_master, index_components. Chỉ OK trả
exit 0; PARTIAL/FAILED/BLOCKED/UNSUPPORTED trả exit 1.

## Kiến trúc và canonical

CLI → run_master_sync → MasterRegistry → adapter version → MasterSnapshot →
validation canonical → compare → MasterStore → JSON.
Orchestrator không chứa URL/tên trường response SSI v3. Price registry, Daily,
Intraday và generic upsert không đổi. Logic mapper v2 cũ đã bỏ; các public sync/map
name giữ dạng wrapper mỏng. Map chưa xác minh bị từ chối. Injection SSI/DB cũ và
scope membership cũ bị từ chối tường minh, không chạy business logic đã nghỉ.

| Bảng / khóa unique | Trường descriptive canonical nguồn được phép sở hữu |
| --- | --- |
| symbols / symbol | market, name |
| securities / symbol | market, stock_name, stock_en_name, sec_type, exchange, issuer, lot_size, listed_share, issue_date, maturity_date, first_trading_date, last_trading_date, tick_price1..4, tick_increment1..4, raw |
| index_master / index_code | index_name, exchange, raw |
| index_components / index_code,symbol | exchange, raw |

Đây là contract DB, không phải mapping SSI đã xác minh. Identifier trim/uppercase,
không trống và theo tập ký tự giới hạn; đúp sau normalize chặn cả dataset. DTO có
cột lạ hoặc status operator bị từ chối. Numeric dùng decimal chính xác, không float,
không âm/NaN/Infinity; ngày ISO. Optional missing giữ NULL/omitted; không ghi NULL
đè giá trị đã có. Không tên fallback, suy diễn board/type/delisting hay membership.
Mỗi adapter tương lai phải chứng minh và giữ phân biệt có ý nghĩa từ nguồn.

## Guard, compare và persistence

MasterSnapshot phải có canonical rows, source count, mapping version, scope đầy đủ
và bằng chứng pagination complete. Contract CLI hiện chỉ full dataset scope
`{"kind":"ALL"}`, một source record cho một canonical row. Lỗi nguồn, paging
không đủ, scope lạ, mapping/count lệch, identity invalid/đúp và source rỗng đều chặn
trước DB write. PREVIEW/unverified không được ghi, cũng không được chọn mặc định.
Dataset sau lỗi không làm mất bằng chứng preview dataset trước đã hoàn thành.

DB read theo thứ tự khóa, trang 100, exact count ổn định; chặn đúp, trang cắt và
vượt 100.000 rows. Validate toàn bộ plan dataset trước mutation đầu tiên.
Classification gồm NEW, CHANGED, UNCHANGED, SOURCE_MISSING, INVALID, CONFLICT;
UNSUPPORTED tường minh ở capability. Count chưa biết là null. JSON gồm capability,
evidence, scope, paging, mapping, số nguồn/canonical/validation/change, classification
chỉ chứa identity/tên cột, planned/actual, readback, mã lỗi an toàn và recovery.
Không in raw response hoặc exception text có thể chứa secret.

Existing symbols giữ status/intraday_status; index_master giữ status. Update chỉ gửi
trường nguồn thay đổi, không gửi status. Insert stock mới inactive/inactive; index
mới inactive. created_at chỉ gửi khi insert symbols; bảng khác gửi updated_at từ
ứng dụng khi thật sự ghi. Generic upsert_symbols/upsert_index_master không đổi
mặc định để tránh ảnh hưởng caller khác.

Insert theo unique key hiện có, ignore_duplicates và kiểm tra row trả về/readback;
không ghi đè concurrent insert. Update compare-and-set theo identity và giá trị
trường descriptive trước sửa. UNCHANGED không ghi lại. SOURCE_MISSING chỉ là vắng
trong snapshot, không xác nhận delisting; không xóa/inactive, không thay membership.

**Transaction: từng row/request, không atomic cả dataset hay nhiều bảng.** Lỗi sau
một số write giữ số ack đã xác nhận và PARTIAL. Write mơ hồ đặt
insert_counts_confirmed=false (áp dụng cả update), dừng không retry. Readback lỗi
báo FAIL. Không rollback/delete/cleanup tự động. DB read nhiều trang không phải
repeatable-read snapshot; guard count/identity/compare-and-set phát hiện sai lệch
nhưng owner nên tránh sync writer chạy chồng. Operator đổi status đồng thời là hợp
lệ; sync không gửi status hay hoàn tác quyết định operator.

## Recovery và thêm version

Khi write/readback lỗi: dừng, kiểm tra identity hiện tại chỉ đọc; chạy lại DRY_RUN,
xem plan rồi owner chạy --write đúng một dataset sau khi nguồn READY. Hàng đã ghi
đúng chuyển UNCHANGED; không retry write mơ hồ tự động.

Thêm v4/v5 (chưa triển khai version giả): thu response thật đã redaction, request,
trường/kiểu/board và bằng chứng mọi trang/terminal/error; viết adapter/mapper riêng
dùng auth và bounded retry chung; không dừng chỉ vì short page. Xác minh total,
trang lặp/sai/thay đổi, malformed, cap và authoritative scope. Trả MasterSnapshot,
missing/unsupported fields và mã lỗi auth/HTTP/rate-limit/timeout/malformed/paging
riêng. Đăng ký MasterCapability theo dataset ở master_registry.py, ban đầu
BLOCKED/PREVIEW; chỉ READY khi có bằng chứng đầy đủ. Thêm fixture nguồn thật và test
canonical/store độc lập, verify read-only. Không cần sửa CLI, bảng, validator hay
persistence. Version number hoặc adapter daily không tự chứng minh master readiness.

## SQL chỉ đọc cho owner

Các câu SQL chỉ được cung cấp, chưa chạy trong task:

```sql
select status,intraday_status,count(*) from public.symbols group by 1,2;
select status,count(*) from public.index_master group by 1;
select symbol,market,name,status,intraday_status,created_at
from public.symbols where symbol='SSI';
select * from public.securities where symbol='SSI';
select * from public.index_master where index_code='VNINDEX';
select * from public.index_components where index_code='VNINDEX' order by symbol;
select indexname,indexdef from pg_indexes where schemaname='public'
and tablename in ('symbols','securities','index_master','index_components');
```

## Báo cáo audit, ảnh hưởng DB và kiểm thử — 26/10/2026

Trước code đã đọc AGENTS/main/CLI, master cũ, helper DB/status/upsert, schema và
migration liên quan master, registry/client/adapter, inspector request/scope,
shared scope, test/fixture hiện có, README hai ngôn ngữ và mọi tham chiếu master
trong repo/workflow/script. Gốc vấn đề: orchestration bị tắt và mapper v2 đoán field;
request inspector không đủ làm mapping. Helper generic bật stock/index mới active,
không phù hợp mặc định sync inactive; giữ helper nguyên, dùng store riêng.

Tái sử dụng symbols, securities, index_master, index_components. Migration/schema:
KHÔNG. Row production chạm trong task: KHÔNG. Backfill giá: KHÔNG. Không bật workflow,
schedule, downstream ingest/feature/research. Script check_complete_ssi_ingest và
các capability bị tắt ngoài master giữ nguyên. Không giữ hai business implementation.

Test canonical là dữ liệu tổng hợp trung lập version, không chứng minh SSI response.
Xác minh nguồn/paging live: NOT_RUN/BLOCKED. Không SSI request live, không Supabase
read/write, không apply migration hay live write smoke. Task ở trạng thái PARTIAL,
không tuyên bố production-ready. Bước tiếp: lấy bằng chứng response/paging master v3
thật có redaction rồi xác minh độc lập từng dataset trước khi viết/promote mapper.

## Kết quả cuối và danh sách file

Test mục tiêu: **91 passed**; toàn bộ: **1115 passed, 7 skipped** (26,65 giây). Bảy test PostgreSQL integration có sẵn cần TEST_DATABASE_URL. Compile/help hai alias/diff check đạt. Kiểm tra truy vấn qua PostgREST SDK thật dùng httpx.MockTransport, không network.

```bash
.venv/bin/python -m pytest -q tests/ingest/test_versioned_master_sync.py tests/ingest/test_master_data_pipeline.py tests/cli/test_capability_retirement.py
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
- `src/README.md`
- `src/README.vi.md`
- `src/cli/README.md`
- `src/cli/README.vi.md`
- `src/cli/__init__.py`
- `src/cli/maintenance.py`
- `src/cli/parser.py`
- `src/ingest/README.md`
- `src/ingest/README.vi.md`
- `src/ingest/master/README.md`
- `src/ingest/master/README.vi.md`
- `src/ingest/master/index_master.py`
- `src/ingest/master/init_symbols.py`
- `src/providers/ssi/README.md`
- `src/providers/ssi/README.vi.md`
- `src/providers/ssi/adapters/README.md`
- `src/providers/ssi/adapters/README.vi.md`
- `tests/cli/test_capability_retirement.py`
- `tests/ingest/test_master_data_pipeline.py`

File tạo:

- `src/ingest/master/contracts.py`
- `src/ingest/master/store.py`
- `src/ingest/master/sync.py`
- `src/providers/ssi/adapters/master_v3.py`
- `src/providers/ssi/master_contract.py`
- `src/providers/ssi/master_registry.py`
- `tests/ingest/test_versioned_master_sync.py`

File xóa: KHÔNG. Bỏ thân mapper legacy; giữ tên import dạng wrapper.
