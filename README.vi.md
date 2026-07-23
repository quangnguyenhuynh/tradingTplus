# Trading T+

Nền tảng dữ liệu Python phục vụ phân tích cổ phiếu Việt Nam với thời gian nắm giữ khoảng T+3 đến T+5 phiên giao dịch.

Repository hiện ở **Phase 0: xây dựng và kiểm chứng dữ liệu**. Độ đúng dữ liệu, hiểu đúng hợp đồng SSI, pipeline có thể chạy lại và kiểm tra completeness được ưu tiên trước signal, backtest, lợi nhuận hoặc AI.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- Tổng quan dự án: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- Trạng thái repository: [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)
- Quyết định kiến trúc: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md)
- Hướng dẫn CLI: [docs/CLI_USAGE.md](docs/CLI_USAGE.md)
- Backfill production: [docs/backfill/README.vi.md](docs/backfill/README.vi.md)
- Ghi chú database: [docs_db_schema.md](docs_db_schema.md)

Khi tài liệu cũ mâu thuẫn với hành vi thực thi, code, schema, migration và test hiện tại là nguồn sự thật.

## Kiến trúc

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
signals
    ↓
backtests
    ↓
alerts
```

Các hợp đồng bắt buộc:

- Pipeline daily và intraday tách biệt.
- Raw data và clean data tách biệt.
- Ingest không tự động tính feature, signal hoặc backtest.
- `stock_daily` là nguồn chuẩn cho feature `1d`.
- `stock_intraday` chỉ lưu `timeframe='1m'`.
- `5m`, `15m`, `60m` được aggregate từ nến clean 1 phút trong feature pipeline.
- Thiết kế được chấp nhận là một bảng `features`, key `(symbol, timeframe, time)`.
- Không biến dữ liệu thiếu hoặc endpoint không hỗ trợ thành dòng dữ liệu giả có giá trị 0.

## Cấu trúc repository

| Đường dẫn | Trách nhiệm |
| --- | --- |
| `main.py` | CLI production. |
| `src/ssi/` | Client SSI REST và streaming. |
| `src/pipeline/` | Master data, ingest, EOD, validation orchestration, backfill và snapshot. |
| `src/database/` | Truy cập Supabase và hợp đồng ghi dữ liệu. |
| `src/validation/` | Validation daily, intraday và streaming. |
| `src/engine/` | Tính feature và các engine research/MVP downstream. |
| `scripts/` | Tool manual, smoke, debug, inspector và maintenance. |
| `migrations/` | Thay đổi database có version. |
| `sql/` | SQL vận hành chạy có chủ đích. |
| `tests/` | Unit test và contract test offline. |
| `.github/workflows/` | CI và workflow lịch/manual. |

Mỗi folder tracked có cặp tài liệu `README.md` tiếng Anh và `README.vi.md` tiếng Việt.

Daily và intraday REST ingest đều có module riêng theo tầng `fetcher -> mapper -> tích hợp validator -> persistence -> service`. `daily.py` và `intraday_ingest.py` là hai batch orchestrator độc lập; `eod.py` chỉ chạy tuần tự hai pipeline rồi kiểm tra completeness. `fetch_one_day.py` legacy là compatibility wrapper mỏng, không phải implementation thứ hai. Xem [hướng dẫn module pipeline](src/pipeline/README.vi.md) để biết đầy đủ cây thư mục, ownership, retry và thứ tự chạy.

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

Không commit credential thật, access token hoặc nội dung `.env`.

## CLI production

```bash
python main.py sync-master-data
python main.py init
python main.py daily [DD/MM/YYYY] --symbols SSI HPG
python main.py intraday-ingest [DD/MM/YYYY] --symbols SSI HPG
python main.py eod [DD/MM/YYYY] --symbols SSI HPG
python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py features --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 1m 5m 15m 60m 1d
python main.py intraday --symbols SSI HPG
python main.py streaming-ingest --symbols SSI --channels quote --timeout 60 --max-messages-per-channel 1
```

Hành vi hiện tại:

- `sync-master-data` / `init`: đọc SSI `Securities`, `SecuritiesDetails`, `IndexList`, `IndexComponents`; ghi `symbols`, `securities`, `indexes`, `index_components`.
- `daily`: chỉ đọc SSI `DailyStockPrice`, `DailyIndex`; ghi `raw_daily`, `stock_daily`, `index_daily` và không đồng bộ bảng index master.
- `intraday-ingest`: đọc SSI `IntradayOhlc` resolution 1 cùng optional context `stock_daily` từ DB; chỉ ghi `raw_intraday` và `stock_intraday` 1m.
- `eod`: daily ingest → intraday ingest → completeness validation.
- `backfill-daily`: chỉ ingest daily trong khoảng bao gồm hai đầu; giữ hành vi index daily hiện có.
- `backfill-intraday`: chỉ ingest intraday 1m; dùng daily context hiện có nhưng không tự tạo.
- `backfill`: chạy xong nhánh daily → nhánh intraday → completeness từng ngày; không tự chạy feature downstream.
- `features`: feature pipeline riêng, hỗ trợ chạy lại.
- `intraday`: alias legacy tính intraday feature; không lấy candle mới.
- `streaming-ingest`: chạy giới hạn và read-only nếu không có `--write`.

## Tool manual

Bắt đầu từ [scripts/README.vi.md](scripts/README.vi.md). Hai SSI inspector riêng:

- [scripts/ssi_api_inspector/README.vi.md](scripts/ssi_api_inspector/README.vi.md)
- [scripts/ssi_streaming_inspector/README.vi.md](scripts/ssi_streaming_inspector/README.vi.md)

Tool debug/inspection phải ưu tiên read-only hoặc dry-run. Mọi thao tác ghi/xoá phải có phạm vi symbol/date rõ ràng.

## Test

```bash
python -m compileall main.py src scripts
python main.py --help
python -m pytest -q
```

Smoke test SSI/Supabase cần credential và mặc định phải read-only, trừ khi chủ đích chạy write test có phạm vi rõ ràng.

## Thay đổi database

Mọi thay đổi schema cần migration trong [`migrations/`](migrations/README.vi.md). Có file migration trong repo không đồng nghĩa production Supabase đã áp dụng migration đó.

## Trạng thái dự án

Signal và backtest hiện là code research/MVP, chưa được xem là logic sản phẩm đã kiểm chứng trong Phase 0. Không suy luận khả năng sinh lợi, win rate hoặc độ sẵn sàng production từ dữ liệu chưa kiểm chứng hoặc tài liệu cũ.

### Phạm vi mã cổ phiếu cho ingest dữ liệu nguồn

`daily`, `intraday-ingest`, `eod`, `backfill-daily`, `backfill-intraday` và `backfill` nhận `--symbols` với ít nhất một giá trị. Khi bỏ qua option, pipeline dùng mọi mã từ nguồn master hiện có. Giá trị explicit được strip, đổi thành chữ hoa và loại trùng theo thứ tự xuất hiện đầu tiên; scope explicit rỗng là không hợp lệ. Scope cổ phiếu của daily không ảnh hưởng ingest index hằng ngày; đồng bộ index master chỉ thuộc `sync-master-data` / `init`. EOD truyền cùng một scope cho daily, intraday và completeness cổ phiếu; backfill dùng lại scope đó cho mọi ngày. Count quan sát index và market context khác vẫn theo toàn ngày. Command `intraday` legacy vẫn là alias feature, không phải ingest candle. Ingest dữ liệu nguồn không tự chạy feature, signal hay backtest.
