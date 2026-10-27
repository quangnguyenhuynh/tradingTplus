# Master chứng khoán hợp nhất vào symbols

[English](README.md)

**Triển khai PARTIAL: owner phải chạy migration A và xác minh live trước cutover.**
public.symbols là đích ghi master duy nhất. Giữ bảng/PK symbol, status,
intraday_status, created_at và FK hiện có; securities vật lý tạm giữ legacy backup.

## Schema, migration và bảo toàn dữ liệu

Giữ symbol/market/name/created_at/status/intraday_status. Thêm nullable:
stock_en_name, sec_type, exchange, issuer, lot_size, listed_share, issue_date,
first_trading_date, last_trading_date, maturity_date, tick_price1..4,
tick_increment1..4, raw JSONB, updated_at. Numeric/date giữ kiểu và precision.
stock_name legacy → name, market → market; không thêm stock_name trùng nghĩa.
Issuer/issue_date/tick chưa có SSI mapping nhưng giữ để migrate legacy không mất dữ
liệu; sync không tự bịa nguồn. NULL không ghi đè giá trị biết; raw xung đột cũng abort.

A: migrations/20261027_expand_symbols_master.sql. Dừng mọi master writer, backup hai
bảng và grants/dependencies. Transaction khóa hai bảng, thêm cột, kiểm tra mọi field
non-NULL xung đột trước insert/update. Không chọn winner mô tả ngầm. Chỉ điền target
NULL; operator status/intraday_status/created_at giữ nguyên tuyệt đối. Legacy-only
insert inactive/inactive, created_at NULL vì không biết thời gian tạo gốc; updated_at
ưu tiên target có sẵn rồi legacy. Rerun idempotent hoặc abort rõ khi có xung đột mới.
Không tạo lại bảng, đổi PK/FK, xóa hoặc chạm giá/feature. CLI Supabase không có sẵn,
migration theo quy ước ngày hiện có của repo; chưa được apply.

Preflight kiểm tra count, overlap và từng field trong mapping SQL; owner xử lý xung
đột riêng có bằng chứng/backup, không overwrite tùy tiện:

```sql
select count(*) from public.symbols;
select count(*) from public.securities;
select t.symbol,t.name,s.stock_name,t.market,s.market
from public.symbols t join public.securities s using(symbol)
where (t.name is not null and s.stock_name is not null and t.name is distinct from s.stock_name)
or (t.market is not null and s.market is not null and t.market is distinct from s.market);
-- Sau A: không identity legacy nào thiếu, đối chiếu metadata/control với backup
select s.symbol from public.securities s left join public.symbols t using(symbol) where t.symbol is null;
select status,intraday_status,count(*) from public.symbols group by 1,2;
```

## Cutover và CLI

Owner chạy A thủ công TRƯỚC deploy code này. Thiếu expansion báo
SYMBOLS_SCHEMA_REQUIRED_APPLY_STAGE_A_OR_CHECK_DB_ACCESS, hướng dẫn filename; không
fallback schema cũ hay partial sync. Select đầy đủ metadata, cast numeric sang text
để tránh SDK float rounding; lỗi quyền DB cũng dừng an toàn.

```bash
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --dry-run
# Owner sau khi kiểm tra toàn bộ preflight:
python main.py sync-master-data --dataset symbols --data-source ssi_v3 --write
python main.py init --dataset symbols --data-source ssi_v3 --dry-run
```

securities là alias DEPRECATED, có requested_dataset, canonical_dataset=symbols và
warning; chỉ một sync vật lý, vẫn cần --write. all preview symbols một lần và hai
index dataset BLOCKED; không write-all. map_security_record nay trả name thay
stock_name. upsert_securities báo lỗi thay thế rõ, không ngầm chuyển đích hoặc giữ
writer thứ hai. Generic upsert_symbols giữ compatibility; guarded sync mới gán
inactive/inactive. Bộ chọn ingest active hiện có không đổi, không tự bật stock,
bond, ETF hay derivative. Control operator không phải bộ lọc chiến lược.

## Mapping và ngoại lệ nguồn có bằng chứng

Dùng client/auth/retry chung, request securitiesByBoard ba board HOSE/HNX/UPCOM.
DTO symbols chứa mọi field được hỗ trợ và raw sanitize. symbolNameVi→name,
symbolNameEn→stock_en_name, board→market/exchange, stockType→sec_type, lotSize/
listedShare và ngày giữ conversion chính xác. Không gộp index, không đoán v4/v5.

Owner quan sát 27/10: 795/414/852, tổng 2061, không phải tổng cố định bắt buộc.
Chỉ đúng record request HOSE, symbol VN50 GROWTH, actual board HOSE, stockType NULL
được loại khỏi scope security vì owner xác nhận cũng có trong indexList. Không
đổi thành VN50GROWTH. Exclusion có identity/lý do/requested board/count; received =
accepted + excluded khi hợp lệ. Identity có khoảng trắng khác vẫn chặn.
Chỉ ngoại lệ request HNX / actual DERIVATIVES / stockType Future được nhận; giữ
market DERIVATIVES, sec_type Future, raw và thống kê actual-market cạnh requested
board. Mismatch khác chặn; derivative mới inactive/inactive.

Đủ cả ba response, tách received/accepted/excluded/invalid/duplicate. Nhận đủ HTTP
body không chứng minh universe toàn thị trường; authoritative completeness vẫn
UNVERIFIED. Giữ guard count giảm mạnh/đúp/malformed/decimal/date, NULL preservation,
compare-and-set/readback/ambiguous-write. Transaction từng row/request, không hứa
atomic nhiều bảng. Source count tính exclusion tường minh, không lặng lẽ bỏ row.

## B và rollback

Chỉ sau A → deploy code → owner kiểm tra count/metadata/control/FK, dry-run/write/
readback/idempotency → audit view/matview/RPC/trigger/FK/job/client → backup phục hồi
được → approval riêng, mới chạy migrations/20261027_retire_securities_optional.sql.
File B mặc định abort. Owner thêm SET LOCAL app.approve_retire_securities =
'owner-reviewed-and-backed-up' sau BEGIN trong transaction thủ công đã review.
DROP RESTRICT, không CASCADE; kiểm tra coverage identity và stored-function refs.
Không thể dùng catalog để chứng minh dynamic SQL/client ngoài không còn phụ thuộc.
Không chạy B tự động chung A. Agent chưa thực thi bất cứ migration production nào.

Rollback app trước; giữ cột mở rộng và identity mới vì có thể có FK. Chỉ phục hồi
mô tả từ backup theo scope đã review; không bulk delete/reload. Rollback B cần restore
bảng securities/data/grants/indexes từ archive và app tương thích, không xóa symbols.

Audit dev 5e22c5c94053fd446d826fd4f87af9412cd7642e. Catalog live chỉ đọc xác nhận FK
stock_intraday/partitions, stock_features, stock_foreign_trading, analog_snapshots,
stock_screener_results tới symbols; không FK securities, view/matview/trigger liên
quan. RPC foreign dùng symbols; không function tham chiếu securities; cron.job vắng.
Không thấy Flutter/consumer securities vật lý ngoài helper master và diagnostic đã
cập nhật. Owner cần audit lại lúc apply; count owner cung cấp không là giả định SQL.

Không write production/live SSI, không backfill giá/feature/signal/strategy/index
capability/schedule. Local SQL execution NOT_RUN do Docker socket không truy cập và
không tải được runtime. Có test SQL structural và test thực thi PostgreSQL disposable
cho CI. Triển khai production giữ PARTIAL đến khi owner chạy A và xác minh live.

## Kết quả và danh sách file

158 passed, 3 skipped (focused); 1203 passed, 10 skipped (full suite). Compile/help/diff check PASS. PostgreSQL migration execution NOT_RUN locally; 3 disposable migration tests + 7 existing integration tests require TEST_DATABASE_URL. SQL structural checks passed. No production migration/write or live SSI call.

```bash
.venv/bin/python -m pytest -q tests/ingest/test_unified_master.py tests/ingest/test_unified_master_postgres.py tests/ingest/test_versioned_master_sync.py tests/ingest/test_ssi_v3_master_adapter.py tests/ingest/test_master_data_pipeline.py
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
- `docs/SSI_V3_MASTER_EVIDENCE.md`
- `docs/SSI_V3_MASTER_EVIDENCE.vi.md`
- `migrations/README.md`
- `migrations/README.vi.md`
- `schema.sql`
- `scripts/checks/check_ssi_ingest_schema.py`
- `scripts/checks/check_supabase.py`
- `src/database/README.md`
- `src/database/README.vi.md`
- `src/database/client.py`
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
- `src/providers/ssi/master_contract.py`
- `tests/ingest/test_ssi_v3_master_adapter.py`
- `tests/ingest/test_versioned_master_sync.py`

File tạo:

- `migrations/20261027_expand_symbols_master.sql`
- `migrations/20261027_retire_securities_optional.sql`
- `tests/ingest/test_unified_master.py`
- `tests/ingest/test_unified_master_postgres.py`

Deleted: NONE. Migration order: A → deploy → owner verification/backups/approval → optional B. Deployment PARTIAL, not applied.
