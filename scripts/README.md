# Scripts manual, smoke test và maintenance

Thư mục `scripts/` chứa các công cụ chạy thủ công phục vụ kiểm tra dữ liệu, smoke test, backfill có phạm vi và snapshot streaming. Đây **không phải** các production workflow chính.

Production pipeline phải chạy qua `main.py`:

```bash
python main.py sync-master-data
python main.py daily [DD/MM/YYYY]
python main.py intraday-ingest [DD/MM/YYYY] --symbols SSI HPG
python main.py eod [DD/MM/YYYY]
python main.py features --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 1m 5m 15m 60m 1d
```

## Nguyên tắc an toàn

- Ưu tiên chạy script read-only hoặc dry-run trước.
- Không thêm script tự động nối ingest → feature → signal → backtest.
- Ingest không tự tính feature; feature phải chạy bằng pipeline riêng.
- Script ghi dữ liệu phải có phạm vi symbol/date rõ ràng.
- Không chạy backfill rộng khi chưa kiểm tra raw data, clean data, schema và completeness.
- Không in token, secret hoặc nội dung `.env`.
- Không tự tạo dữ liệu cho cuối tuần, ngày nghỉ, API rỗng hoặc endpoint SSI không hỗ trợ.

## Ký hiệu

| Nhãn | Ý nghĩa |
|---|---|
| `READ-ONLY` | Chỉ đọc API hoặc database, không ghi dữ liệu. |
| `DRY-RUN DEFAULT` | Mặc định không ghi; chỉ ghi khi truyền `--write`. |
| `WRITES DB` | Có ghi database khi chạy; phải kiểm tra phạm vi trước. |

## Tổng quan

| Script | Mức độ | Mục đích |
|---|---|---|
| `check_supabase.py` | `READ-ONLY` | Kiểm tra kết nối Supabase và khả năng đọc các bảng core. |
| `check_ssi_ingest_schema.py` | `READ-ONLY` | Kiểm tra các bảng/cột bắt buộc của SSI ingest qua Supabase. |
| `check_complete_ssi_ingest.py` | `DRY-RUN DEFAULT` | Smoke test SSI API, mapper raw/clean, securities, indexes và daily index. |
| `check_ingest.py` | `READ-ONLY` | Kiểm tra completeness của dữ liệu ingest theo ngày. |
| `eod_dry_run.py` | `READ-ONLY` | Chạy kiểm tra EOD mà không ghi dữ liệu. |
| `fetch_one_day.py` | `DRY-RUN DEFAULT` | Test một mã trong một ngày; chỉ ghi khi có `--write`. |
| `backfill_sample.py` | `WRITES DB` | Chạy backfill theo khoảng ngày và danh sách mã bắt buộc. |
| `run_features.py` | `WRITES DB` | Chạy feature engine thủ công trên dữ liệu clean hiện có. |
| `snapshot_stream.py` | `DRY-RUN DEFAULT` | Nhận snapshot SSI streaming; chỉ ghi khi có `--write`. |
| `snapshot_orderbook.py` | `DRY-RUN DEFAULT` | Nhận snapshot orderbook từ quote stream; chỉ ghi khi có `--write`. |

## 1. Kiểm tra Supabase

### `check_supabase.py`

**Mức độ:** `READ-ONLY`

Kiểm tra:

- Có `SUPABASE_URL` và `SUPABASE_SERVICE_KEY`.
- Kết nối Supabase thành công.
- Có thể đọc các bảng core như `securities`, `raw_daily`, `stock_daily`, `raw_intraday`, `stock_intraday`, `indexes`, `index_daily`, `foreign_trading`, `orderbook_snapshot` và `features`.

```bash
python scripts/check_supabase.py
```

Script không insert, update hoặc delete dữ liệu và không in giá trị secret.

## 2. Kiểm tra schema SSI ingest

### `check_ssi_ingest_schema.py`

**Mức độ:** `READ-ONLY`

Kiểm tra sự tồn tại của các bảng và cột cần thiết cho SSI ingest bằng các câu `select(...).limit(1)`. Script chỉ in hướng dẫn SQL để kiểm tra unique index; không tự chạy migration.

```bash
python scripts/check_ssi_ingest_schema.py
```

Nên chạy sau khi áp dụng migration SSI ingest và trước khi chạy smoke test có ghi dữ liệu.

## 3. Smoke test SSI ingest đầy đủ

### `check_complete_ssi_ingest.py`

**Mức độ:** `DRY-RUN DEFAULT`

Kiểm tra một symbol/ngày qua các phần:

- `DailyStockPrice` → `raw_daily` và `stock_daily`.
- `IntradayOhlc` → số lượng nến 1m.
- `SecuritiesDetails` → `securities`.
- `IndexList` → `indexes`.
- `DailyIndex` → `index_daily`.

Chạy read-only:

```bash
python scripts/check_complete_ssi_ingest.py --symbol SSI
python scripts/check_complete_ssi_ingest.py --symbol SSI --date 10/07/2026
```

Ghi daily/master data với ngày cụ thể:

```bash
python scripts/check_complete_ssi_ingest.py \
  --symbol SSI \
  --date 10/07/2026 \
  --write
```

Ghi thêm intraday:

```bash
python scripts/check_complete_ssi_ingest.py \
  --symbol SSI \
  --date 10/07/2026 \
  --write \
  --write-intraday
```

Lưu ý:

- `--write` bắt buộc phải có `--date`.
- Script từ chối ngày cuối tuần hoặc tương lai, trừ khi truyền `--force` có chủ đích.
- Không dùng `--force` để tạo dữ liệu giả cho ngày không giao dịch.
- Intraday chỉ được lưu với `timeframe='1m'`.

## 4. Kiểm tra completeness ingest

### `check_ingest.py`

**Mức độ:** `READ-ONLY`

In thống kê ingest theo ngày và các phần còn thiếu, dựa trên `src.pipeline.ingest_check.check_ingest`.

```bash
python scripts/check_ingest.py --date 10/07/2026
```

Dùng script này để phát hiện thiếu dữ liệu; không hardcode một số lượng nến cố định làm chuẩn cho mọi ngày.

## 5. EOD dry-run

### `eod_dry_run.py`

**Mức độ:** `READ-ONLY`

Kiểm tra trạng thái dữ liệu EOD cho symbol/timeframe mà không ghi database.

```bash
python scripts/eod_dry_run.py \
  --date 10/07/2026 \
  --symbols SSI HPG \
  --timeframes 1m 5m 15m 60m 1d \
  --json
```

Timeframe `1d` phải lấy từ `stock_daily`; không được tính từ intraday.

## 6. Test một mã, một ngày

### `fetch_one_day.py`

**Mức độ:** `DRY-RUN DEFAULT`

Chạy dry-run để xem SSI có daily và bao nhiêu nến intraday:

```bash
python scripts/fetch_one_day.py \
  --symbol SSI \
  --date 10/07/2026 \
  --dry-run
```

Ghi raw/clean data cho đúng một mã và một ngày:

```bash
python scripts/fetch_one_day.py \
  --symbol SSI \
  --date 10/07/2026 \
  --write
```

Không dùng file này để backfill nhiều mã hoặc khoảng ngày dài.

## 7. Backfill có phạm vi

### `backfill_sample.py`

**Mức độ:** `WRITES DB`

Chạy production backfill với khoảng ngày và danh sách symbol bắt buộc:

```bash
python scripts/backfill_sample.py \
  --from-date 2026-07-01 \
  --to-date 2026-07-10 \
  --symbols SSI FPT
```

Yêu cầu:

- `--from-date` và `--to-date`: định dạng `YYYY-MM-DD`.
- `--symbols`: phải chỉ rõ danh sách mã.
- Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.
- Không chạy trước khi schema check, SSI smoke test và completeness check đạt yêu cầu.

Script này ghi dữ liệu ngay khi chạy; không có chế độ dry-run.

## 8. Chạy feature thủ công

### `run_features.py`

**Mức độ:** `WRITES DB`

Chạy feature engine độc lập với ingest:

```bash
python scripts/run_features.py \
  --mode incremental \
  --symbols SSI HPG \
  --timeframes 1m 5m 15m 60m 1d
```

Full rerun:

```bash
python scripts/run_features.py \
  --mode full \
  --symbols SSI \
  --timeframes 1d
```

Lưu ý:

- Script đọc `stock_intraday` 1m và `stock_daily`, sau đó ghi bảng `features`.
- `5m`, `15m`, `60m` được aggregate từ 1m trong feature pipeline.
- `1d` lấy từ `stock_daily`.
- Script không chạy signal hoặc backtest sau khi tính feature.
- Với production flow có target date rõ ràng, ưu tiên `python main.py features ...`.

## 9. Snapshot SSI streaming

### `snapshot_stream.py`

**Mức độ:** `DRY-RUN DEFAULT`

Nhận snapshot market stream cho symbol và index:

```bash
python scripts/snapshot_stream.py \
  --symbols SSI HPG \
  --indexes VNINDEX VN30 \
  --timeout 60 \
  --limit 20 \
  --debug
```

Ghi snapshot:

```bash
python scripts/snapshot_stream.py \
  --symbols SSI HPG \
  --indexes VNINDEX VN30 \
  --timeout 60 \
  --limit 20 \
  --write
```

Nếu không truyền `--symbols`, script đọc danh sách mã từ Supabase rồi giới hạn bằng `--limit`.

### `snapshot_orderbook.py`

**Mức độ:** `DRY-RUN DEFAULT`

Nhận quote/orderbook snapshot từ SSI streaming:

```bash
python scripts/snapshot_orderbook.py SSI HPG --timeout 30 --debug
```

Ghi snapshot:

```bash
python scripts/snapshot_orderbook.py SSI HPG --timeout 30 --write
```

Orderbook ở đây đến từ quote streaming payload, không phải một public REST `MarketDepth` endpoint tự tạo.

## 10. SSI inspectors

Hai inspector chỉ phục vụ Phase 0, mặc định read-only và có tài liệu riêng:

- [`ssi_api_inspector/README.md`](ssi_api_inspector/README.md): xem raw response của các SSI FastConnect Data REST endpoint được tài liệu hỗ trợ.
- [`ssi_streaming_inspector/README.md`](ssi_streaming_inspector/README.md): xem SignalR negotiate, raw frames, wrapper và decoded streaming payload.

Inspectors không phải production ingest pipeline, không tính feature và không ghi database.

## Thứ tự kiểm tra khuyến nghị

```text
1. check_supabase.py
2. check_ssi_ingest_schema.py
3. ssi_api_inspector hoặc ssi_streaming_inspector khi cần xem raw payload
4. check_complete_ssi_ingest.py ở chế độ read-only
5. fetch_one_day.py --dry-run
6. chạy ingest có phạm vi
7. check_ingest.py hoặc eod_dry_run.py
8. run feature riêng khi raw/clean/completeness đã được kiểm chứng
```

Không đánh giá signal, backtest, win rate hoặc khả năng sinh lợi khi dữ liệu chưa được kiểm chứng.