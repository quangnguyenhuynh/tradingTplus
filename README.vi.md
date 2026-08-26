# Trading T+

Nền tảng dữ liệu Python phục vụ phân tích cổ phiếu Việt Nam với thời gian nắm giữ khoảng T+3 đến T+5 phiên giao dịch.

Repository đã đóng **Phase 0: xây dựng và kiểm chứng dữ liệu** với trạng thái `COMPLETE_WITH_NOTES`. Độ đúng dữ liệu, hiểu đúng hợp đồng SSI, pipeline có thể chạy lại và kiểm tra completeness vẫn được ưu tiên trước signal, backtest, lợi nhuận hoặc AI.

## Tài liệu

- English: [README.md](README.md)
- Tổng quan dự án: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- Trạng thái repository: [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)
- Quyết định kiến trúc: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md)
- Quy ước dữ liệu: [docs/DATA_CONVENTIONS.vi.md](docs/DATA_CONVENTIONS.vi.md)
- Hướng dẫn CLI: [docs/CLI_USAGE.md](docs/CLI_USAGE.md)
- Tài liệu feature: [src/features/README.vi.md](src/features/README.vi.md)
- Hợp đồng historical analog Phase 1: [docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md](docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md)
- Hợp đồng database: [schema.sql](schema.sql) và [migrations/](migrations/README.vi.md)

Khi tài liệu cũ mâu thuẫn với hành vi thực thi, code, schema, migration và test hiện tại là nguồn sự thật.

## Hợp đồng kiến trúc

```text
Nguồn SSI
    ↓
raw data
    ↓
clean data
    ↓
validation và completeness
    ↓
stock_features
    ↓
nghiên cứu historical analog Phase 1 (core EOD V1 đã triển khai)
```

Các quy tắc bắt buộc:

- Pipeline daily và intraday tách biệt.
- Raw data và clean data tách biệt.
- Ingest không tự động tính feature. Feature không tự động chạy logic signal hoặc backtest.
- `stock_daily` là nguồn chuẩn cho feature `1d`.
- `stock_intraday` chỉ lưu nến nguồn chuẩn `timeframe='1m'`.
- Feature production chỉ lưu `1d`, `15m`, `60m`.
- `15m` và `60m` được aggregate từ clean 1m trong memory.
- Không lưu row feature `1m` và `5m` vào bảng `stock_features`.
- Mọi output feature vẫn dùng một bảng với key `(symbol, timeframe, time)`.
- Không tạo dữ liệu giả bằng cách đổi dữ liệu thiếu thành 0.

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Biến môi trường cần thiết phụ thuộc command:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
SSI_CONSUMER_ID=
SSI_CONSUMER_SECRET=
```

Không commit credential thật, token hoặc nội dung `.env`.

## CLI production

Ingest dữ liệu nguồn:

```bash
python main.py sync-master-data
python main.py init
python main.py daily [DD/MM/YYYY] --symbols SSI HPG
python main.py intraday-ingest [DD/MM/YYYY] --symbols SSI HPG
python main.py eod [DD/MM/YYYY] --symbols SSI HPG
python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py refill --symbol SSI --from DD/MM/YYYY --to DD/MM/YYYY
```

Feature chạy riêng và có chủ đích:

```bash
python main.py features-daily --date DD/MM/YYYY --symbols SSI HPG
python main.py features-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --date DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m
python main.py features-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 15m 60m
python main.py features --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m 1d
```

Feature có ba semantics tách biệt:

- **Full** đọc toàn bộ lịch sử nguồn trong scope, tính lại và upsert toàn bộ kết
  quả; không delete feature cũ trước.
- **Incremental** đọc watermark `stock_features.time` mới nhất riêng cho từng
  symbol/timeframe. Daily dùng warm-up 5 năm từ `stock_daily`; intraday dùng 250
  phiên giao dịch thực tế gần nhất từ nến clean 1m. Pipeline tính trên toàn bộ
  window đã load nhưng chỉ ghi row sau watermark đến target date (hoặc chỉ
  target date nếu chưa có watermark).
- **Replace / rebuild-clean** dành riêng cho rebuild atomic có scope chính xác.
  CLI bắt buộc đúng một symbol, một timeframe thuộc `1d`/`15m`/`60m`, đủ hai
  mốc range và `start <= end`. Application compute và validate trước đúng một RPC atomic; phải deploy migration mới trước khi dùng.

Range command vẫn là backfill explicit. Ingest không tự gọi bất kỳ feature mode nào.
`refill` là ngoại lệ orchestration được yêu cầu rõ ràng: maintenance flow cho đúng
một mã, chạy source backfill và completeness trước rồi upsert feature `1d`, `15m`,
`60m`. Command không sync master data hay chạy phân tích downstream.

Alias legacy chỉ ghi feature 15m/60m:

```bash
python main.py intraday --symbols SSI HPG --timeframes 15m 60m
```

Các command sau bị từ chối có chủ đích:

```bash
python main.py features-intraday --timeframes 1m
python main.py features-intraday --timeframes 5m
python main.py features --timeframes 1m 5m 1d
```

Dùng `intraday-ingest` để lưu nến nguồn 1m. Xem [tài liệu feature](src/features/README.vi.md) để phân biệt nến nguồn 1m và row feature được lưu.

## Test

```bash
python -m compileall main.py src scripts
python main.py --help
python -m pytest -q
```

Smoke test SSI/Supabase cần credential và mặc định phải read-only, trừ khi chủ đích chạy write test có phạm vi rõ ràng.

## Ảnh hưởng database của chính sách timeframe

Không cần migration schema. Các row `stock_features` timeframe `1m` hoặc `5m` đã tồn tại không bị tự động xóa. Việc cleanup phải là thao tác database riêng, có phạm vi rõ ràng. Không cần backfill dữ liệu nguồn.

## Trạng thái dự án

Phase 0 đã đóng ở trạng thái `COMPLETE_WITH_NOTES`. Thiết kế Phase 1 đã được
chốt: tại mỗi checkpoint, một mã chỉ so với lịch sử của chính mã đó ở cùng
checkpoint rồi thống kê outcome cấu hình (V1 H+1/H+3/H+5; EOD V2 thêm H+10).
Không được gom mẫu nhiều mã; thiếu
evidence phải trả `insufficient_sample`.

Runtime, CLI, test và schema snapshot của hướng strategy/rule, signal và
backtest cũ đã bị xóa. Core Historical Analog EOD V1 đã được triển khai; profile
draft và distance threshold null vẫn chặn approval/query production. Xem
[spec Phase 1](docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).

### Contract rebuild feature
Daily feature phân trang toàn bộ row `stock_daily` phù hợp. `full` vẫn upsert không delete; `incremental` dùng watermark riêng với warm-up daily 5 năm hoặc intraday 250 phiên quan sát; `replace` (`rebuild-clean`) compute và validate đúng một symbol/timeframe/range ngày Việt Nam inclusive trước một RPC atomic. Incremental không có output là no-op thành công. Phải deploy `migrations/20260802_atomic_replace_features.sql` trước khi dùng replace.

Pagination tiếp tục sau trang ngắn do server cap, tăng offset theo số row thực
trả và kết thúc ở trang rỗng (hoặc limit chính xác). Toàn bộ phiên intraday cũ
nhất được chọn vẫn được giữ khi nằm qua boundary hai trang. Test lịch sử dài
deterministic so sánh mọi cột persisted cho `1d`, `15m`, `60m`; xem
[báo cáo kiểm chứng Phase 0](docs/phase0/PHASE0_VALIDATION_REPORT.vi.md). Phase 0
đã **COMPLETE_WITH_NOTES**: owner đã kiểm tra schema production apply thủ công
và sample lineage/reconciliation live có phạm vi. Report ghi rõ rủi ro calendar
và lưu evidence còn lại; core Historical Analog EOD V1 đã triển khai; validation cuối và approval vẫn còn pending.

### Pipeline nguồn index daily

Dùng `index-daily`, `index-backfill` và lệnh chỉ đọc `index-check` cho SSI DailyIndex. Hợp đồng phân lớp là scope `index_master` → bằng chứng payload `index_raw_daily` → `index_daily` đã validate; EOD kết hợp flow này nhưng không tính feature hoặc kết quả research downstream. Xem [hướng dẫn sử dụng CLI](docs/CLI_USAGE.vi.md).
Identity và primary key của bảng chuẩn hóa `index_daily` là
`(index_code, trading_date)`: mỗi index chỉ có một dòng trong một ngày giao dịch.

Index Daily Feature V1 được tách riêng có chủ đích khỏi ingest và stock feature:
pipeline đọc clean `index_daily` và ghi bảng riêng `index_features_daily`. Dùng
`index-features-preview`, `index-features-daily`, `index-features-backfill` và
`index-features-check` chỉ đọc; xem [hướng dẫn index feature](src/index_features/README.vi.md).

Trước khi ingest, có thể dùng `index-preview` để kiểm tra trực tiếp SSI mà không
khởi tạo database client hoặc ghi row raw/clean. Mọi ngày của CLI index đều nhận `YYYY-MM-DD` hoặc
`DD/MM/YYYY`; range là inclusive. Giá trị SSI bị thiếu vẫn là `null` trong JSON
và hiển thị `-` trong bảng dễ đọc. `--indexes` là bắt buộc và nhận một giá trị
phân tách bằng dấu phẩy; preview không lấy scope bị bỏ trống từ database.

```bash
python main.py index-preview --date 2026-08-24 --indexes VNINDEX
python main.py index-preview --from 2026-08-01 --to 2026-08-24 --indexes VNINDEX,HNXINDEX
python main.py index-preview --date 2026-08-24 --indexes VNINDEX --raw
python main.py index-preview --date 2026-08-24 --indexes VNINDEX --json
```

Preview raw giữ nguyên toàn bộ item SSI và kèm tóm tắt mapping; JSON chuẩn hóa
chứa mọi field clean của `index_daily`, đồng thời giữ giá trị thiếu là `null`.
Ma trận audit đầy đủ 23 field từ source sang raw và clean, gồm các alias và field
`Time` chủ ý chỉ lưu raw, nằm trong
[SSI DailyIndex field mapping](docs/SSI_DAILY_INDEX_MAPPING.md).

`--raw` in các row payload SSI do client phân trang hiện có trả về; `--json` in
record đã normalize. Command không insert, upsert, delete, tính feature hoặc
chạy signal/backtest. Hãy preview trước, kiểm tra field và giá trị, chạy
`index-daily` hoặc `index-backfill`, rồi chạy `index-check`.

### Triển khai đổi tên bảng cổ phiếu

Triển khai ứng dụng cùng `migrations/20260826_standardize_stock_table_names.sql` trong maintenance window: dừng scheduled/manual writer, chạy migration thủ công trên Supabase, kiểm tra các truy vấn read-only và PostgREST schema reload, triển khai code này, smoke-test đường đọc/ghi, rồi mới bật lại writer. Migration giữ nguyên mọi row và không cần backfill; không triển khai code trước khi đổi tên database hoặc chạy lại code cũ sau đó.
