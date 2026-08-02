# Trading T+

Nền tảng dữ liệu Python phục vụ phân tích cổ phiếu Việt Nam với thời gian nắm giữ khoảng T+3 đến T+5 phiên giao dịch.

Repository hiện ở **Phase 0: xây dựng và kiểm chứng dữ liệu**. Độ đúng dữ liệu, hiểu đúng hợp đồng SSI, pipeline có thể chạy lại và kiểm tra completeness được ưu tiên trước signal, backtest, lợi nhuận hoặc AI.

## Tài liệu

- English: [README.md](README.md)
- Tổng quan dự án: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- Trạng thái repository: [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)
- Quyết định kiến trúc: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md)
- Quy ước dữ liệu: [docs/DATA_CONVENTIONS.vi.md](docs/DATA_CONVENTIONS.vi.md)
- Hướng dẫn CLI: [docs/CLI_USAGE.md](docs/CLI_USAGE.md)
- Tài liệu feature: [src/features/README.vi.md](src/features/README.vi.md)
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
features
    ↓
nghiên cứu downstream trong tương lai (chưa triển khai)
```

Các quy tắc bắt buộc:

- Pipeline daily và intraday tách biệt.
- Raw data và clean data tách biệt.
- Ingest không tự động tính feature. Feature không tự động chạy logic signal hoặc backtest.
- `stock_daily` là nguồn chuẩn cho feature `1d`.
- `stock_intraday` chỉ lưu nến nguồn chuẩn `timeframe='1m'`.
- Feature production chỉ lưu `1d`, `15m`, `60m`.
- `15m` và `60m` được aggregate từ clean 1m trong memory.
- Không lưu row feature `1m` và `5m` vào bảng `features`.
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
- **Incremental** đọc watermark `features.time` mới nhất riêng cho từng
  symbol/timeframe. Daily dùng warm-up 5 năm từ `stock_daily`; intraday dùng 250
  phiên giao dịch thực tế gần nhất từ nến clean 1m. Pipeline tính trên toàn bộ
  window đã load nhưng chỉ ghi row sau watermark đến target date (hoặc chỉ
  target date nếu chưa có watermark).
- **Replace / rebuild-clean** dành riêng cho rebuild atomic có scope chính xác.
  CLI bắt buộc đúng một symbol, một timeframe thuộc `1d`/`15m`/`60m`, đủ hai
  mốc range và `start <= end`. Application compute và validate trước đúng một RPC atomic; phải deploy migration mới trước khi dùng.

Range command vẫn là backfill explicit. Ingest không tự gọi bất kỳ feature mode nào.

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

Không cần migration schema. Các row `features` timeframe `1m` hoặc `5m` đã tồn tại không bị tự động xóa. Việc cleanup phải là thao tác database riêng, có phạm vi rõ ràng. Không cần backfill dữ liệu nguồn.

## Trạng thái dự án

Code signal và backtest MVP legacy đã được xóa. Hai tầng này sẽ được thiết kế lại ở phase sau khi hợp đồng data và feature được kiểm chứng; hiện không có đường chạy signal hoặc backtest.

### Contract rebuild feature
Daily feature phân trang toàn bộ row `stock_daily` phù hợp. `full` vẫn upsert không delete; `incremental` dùng watermark riêng với warm-up daily 5 năm hoặc intraday 250 phiên quan sát; `replace` (`rebuild-clean`) compute và validate đúng một symbol/timeframe/range ngày Việt Nam inclusive trước một RPC atomic. Incremental không có output là no-op thành công. Phải deploy `migrations/20260802_atomic_replace_features.sql` trước khi dùng replace.

Pagination tiếp tục sau trang ngắn do server cap, tăng offset theo số row thực
trả và kết thúc ở trang rỗng (hoặc limit chính xác). Toàn bộ phiên intraday cũ
nhất được chọn vẫn được giữ khi nằm qua boundary hai trang. Test lịch sử dài
deterministic so sánh mọi cột persisted cho `1d`, `15m`, `60m`; xem
[báo cáo kiểm chứng Phase 0](docs/phase0/PHASE0_VALIDATION_REPORT.vi.md). Phase 0
hiện **BLOCKED**, chưa hoàn thành, vì thiếu evidence SSI/live/production bắt buộc.
