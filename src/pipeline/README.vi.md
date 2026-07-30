# Data pipelines

Production ingest được tách thành các tầng fetch, mapping, tích hợp validation, persistence và orchestration rõ ràng. Daily và intraday là hai pipeline độc lập; EOD chỉ chạy tuần tự và kiểm tra completeness.

## Cây thư mục và trách nhiệm

```text
src/pipeline/
├── daily_fetcher.py          # chỉ gọi SSI DailyStockPrice
├── daily_mapper.py           # payload -> record raw_daily / stock_daily
├── daily_persistence.py      # chỉ ghi raw_daily / stock_daily
├── daily_service.py          # fetch -> map -> validate -> persist một mã/ngày
├── daily.py                  # batch orchestrator daily public
├── intraday_fetcher.py       # chỉ gọi SSI IntradayOhlc resolution 1
├── intraday_mapper.py        # payload -> raw_intraday / stock_intraday 1m
├── intraday_persistence.py   # chỉ ghi raw_intraday / stock_intraday
├── intraday_service.py       # fetch -> map -> validate -> deduplicate -> persist
├── intraday_ingest.py        # batch orchestrator intraday public
├── fetch_one_day.py          # wrapper/re-export compatibility mỏng
├── eod.py                    # daily -> intraday -> completeness
├── ingest_check.py           # báo cáo completeness/consistency
├── date_utils.py             # parse/kiểm tra ngày thị trường Việt Nam
├── init_symbols.py           # đồng bộ master data
├── index_data.py             # ingest index master/daily
├── foreign_trading.py        # writer compatibility legacy explicit; không thuộc daily ingest thường
├── backfill.py               # nhánh daily/intraday độc lập + completeness kết hợp
├── intraday.py               # alias feature legacy, không ingest candle
├── eod_dry_run.py            # utility preview EOD/feature read-only
├── streaming_snapshot.py     # streaming capture có giới hạn
└── orderbook_snapshot.py     # mapping orderbook từ quote stream
```

Các module streaming, index, master data, compatibility feature và dry-run vẫn tách khỏi daily/intraday REST ingest.

## Trình tự daily

Public entrypoint: `daily_run()` / `run_daily_ingest()` trong `daily.py`; CLI `python main.py daily [DD/MM/YYYY] [--symbols SSI HPG]`.

1. Resolve và validate ngày theo thị trường Việt Nam.
2. `daily_fetcher.py` gọi SSI `DailyStockPrice` đúng một lần cho mỗi mã.
3. `daily_mapper.py` tạo record giữ payload nguồn cho `raw_daily` và candidate chuẩn hóa cho `stock_daily`; field thiếu giữ `None`, còn placeholder `0` của SSI cho giá tham chiếu/trần/sàn trở thành `NULL` ở clean data mà không thay đổi raw payload.
4. `daily_service.py` ghi raw evidence qua `daily_persistence.py`.
5. `daily_service.py` gọi validator `validate_daily_record` hiện có.
6. Clean candidate hợp lệ được ghi vào `stock_daily` qua `daily_persistence.py`. Price context bị thiếu không chặn row OHLCV hợp lệ; dải OHLC đồng nhất nằm hoàn toàn cùng một phía ngoài source limits được giữ dưới dạng corporate-action warning, còn vi phạm limit đơn lẻ vẫn blocking.
7. Các field mua, bán, net và room khối ngoại cuối ngày nằm trong row `stock_daily`; daily ingest thông thường không ghi `foreign_trading`.
8. `daily.py` không gọi `DailyIndex`, `IndexList`, `IndexComponents` và không ghi `index_daily`, `indexes`, `index_components`.

`stock_daily` là nguồn canonical cho dữ liệu daily, bao gồm dữ liệu giao dịch khối ngoại và room cuối ngày. `foreign_trading` là bảng legacy và không còn được daily ingest ghi dữ liệu mới; helper compatibility explicit vẫn được giữ lại. Snapshot khối ngoại intraday vẫn là streaming dataset riêng.

## Trình tự intraday

Public entrypoint: `run_intraday_ingest()` trong `intraday_ingest.py`; CLI `python main.py intraday-ingest [DD/MM/YYYY] [--symbols ...]`.

1. Resolve ngày và scope symbol explicit hoặc active.
2. Đọc daily context tùy chọn từ `stock_daily`; bước này không fetch hay ghi daily.
3. `intraday_fetcher.py` gọi SSI `IntradayOhlc` resolution 1.
4. `intraday_mapper.py` hiểu timestamp nguồn theo `Asia/Ho_Chi_Minh`, đổi sang UTC, loại timestamp sai và tạo raw/clean candidate.
5. Mapper chỉ tạo `timeframe='1m'`; `value` là ước tính `round(close * volume)` và giữ `None` nếu đầu vào thiếu/sai.
6. `intraday_service.py` ghi raw evidence qua `intraday_persistence.py`, gọi validator record/batch hiện có, deduplicate theo `(symbol, timeframe, time)` khi validator báo trùng, rồi ghi clean hợp lệ.

Timeframe intraday cao hơn chỉ được aggregate trong feature pipeline và không ghi vào `stock_intraday`.

Validation gap intraday chỉ chuẩn hóa timestamp thành minute bucket trong bộ nhớ; timestamp raw và clean không bị thay đổi. Bucket trống/thiếu chỉ được kiểm tra trong các đoạn khớp lệnh liên tục `09:00-11:29` và `13:00-14:29` (`Asia/Ho_Chi_Minh`). Các phút nghỉ trưa và khoảng ATC `14:30-14:44` trước kết quả đóng cửa SSI vào khoảng `14:45` bị loại khỏi phép đếm. Validator sort nội bộ để kiểm tra gap nhưng vẫn báo rõ input không sort.

`INTRADAY_MISSING_INTERVAL` có nghĩa là **minute bucket trống/thiếu quan sát được**. Chỉ từ IntradayOhlc không thể phân biệt phút không có giao dịch với source omission. Vì vậy gap ngắn, rời rạc vẫn được đếm trong `missing_interval_count`, `missing_minutes` và `empty_minute_bucket_count`, nhưng tự nó không làm completeness fail và không tạo candle giả. Duplicate và mất coverage có tính cấu trúc vẫn tạo `WARNING`/`PARTIAL`. Heuristic ban đầu là ngưỡng data-quality minh bạch, không phải quy tắc SSI chính thức: gap liên tục ít nhất 15 phút, tổng ít nhất 30 phút trống, thiếu phiên sáng/chiều, hoặc first/last coverage lệch vào trong quá 15 phút. Không dùng một candle count cố định chung.

## Trình tự EOD

Public entrypoint: `run_eod_pipeline()` trong `eod.py`; CLI `python main.py eod [DD/MM/YYYY] [--symbols SSI HPG]`.

```text
daily ingest -> intraday ingest -> kiểm tra completeness -> OK/PARTIAL/FAILED
```

EOD giữ nguyên ranh giới daily/intraday. EOD không tính feature, không chạy signal và không chạy backtest.

## Trình tự backfill

`run_daily_backfill_pipeline()` và `run_intraday_backfill_pipeline()` chỉ chạy source ingest tương ứng cho từng ngày thường hợp lệ. `run_backfill_pipeline()` chạy hết khoảng daily, rồi hết khoảng intraday, rồi completeness có scope từng ngày; không gọi EOD trực tiếp. Mọi khoảng gồm hai đầu, báo cáo cuối tuần, cô lập lỗi theo ngày và không chạy engine downstream. Xem [`docs/backfill/README.vi.md`](../../docs/backfill/README.vi.md).

## Raw, clean, validation và persistence

| Dataset | Tạo record | Tích hợp validation | Ghi dữ liệu |
| --- | --- | --- | --- |
| `raw_daily` | `daily_mapper.py` | giữ raw evidence trước clean validation | `daily_persistence.py` |
| `stock_daily` | `daily_mapper.py` | `daily_service.py` + daily validator hiện có | `daily_persistence.py` |
| `raw_intraday` | `intraday_mapper.py` | giữ raw evidence trước clean validation | `intraday_persistence.py` |
| `stock_intraday` | `intraday_mapper.py` | `intraday_service.py` + intraday validator hiện có | `intraday_persistence.py` |

## Compatibility wrapper

`fetch_one_day.py` được giữ làm compatibility module mỏng cho import cũ và script có scope rõ. File re-export helper fetcher/mapper legacy và compose daily/intraday service public; không còn implementation mapping, validation hay persistence trùng lặp. Code mới phải import module theo tầng tương ứng.

Import legacy `backfill(...)` đã deprecated và delegate sang `run_backfill_pipeline()`; symbol scope legacy tùy chọn được delegate sang backfill production; future override vẫn bị từ chối.

## Error và retry

- Fetcher trả kết quả SSI và không nuốt lỗi service/DB.
- Response SSI rỗng không tạo raw/clean giả.
- Timestamp sai bị loại, không thay bằng thời gian hiện tại.
- Service gắn context symbol/date và giữ summary contract hiện có.
- Retry HTTP có giới hạn vẫn thuộc `src/ssi/api.py`; retry/backoff DB có giới hạn vẫn thuộc `src/database/client.py`.
- Persistence tiếp tục dùng DB public methods và conflict keys hiện có.

## Chạy test

```bash
python -m pytest -q tests/ingest/test_fetch_one_day.py
python -m pytest -q tests/ingest/test_intraday_ingest_pipeline.py
python -m pytest -q tests/validation/test_intraday_validator.py
python -m pytest -q tests/ingest/test_ingest_check.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q
```

Ingest không bao giờ tự tính feature, sinh signal hoặc chạy backtest. Các bước downstream này chỉ chạy bằng command explicit.

## Scope mã cổ phiếu dùng chung

`daily`, `intraday-ingest`, `eod`, completeness, `backfill-daily`, `backfill-intraday` và `backfill` dùng một hợp đồng chuẩn hóa: bỏ scope thì dùng nguồn symbol master hiện có; giá trị explicit được strip, đổi chữ hoa, loại trùng theo thứ tự xuất hiện đầu tiên, và scope explicit rỗng làm phát sinh `ValueError`. Symbol explicit được giữ thay vì âm thầm loại bỏ vì repository không có hợp đồng validation active/inactive riêng đáng tin cậy. EOD truyền cùng scope cho cả ba bước dữ liệu nguồn, completeness có scope lọc row cổ phiếu ngay trong query database, và backfill dùng lại scope đã chuẩn hóa cho mọi ngày. `index_daily_count` deprecated luôn bằng `0` và không query DB; đồng bộ index master chỉ thuộc `sync-master-data` / `init`.
# Timestamp tại persistence boundary

Các timestamp persistence của pipeline do application tạo theo `Asia/Ho_Chi_Minh`, ở dạng ISO 8601 với offset `+07:00` rõ ràng.
`time`, `source_time` và `trading_date` vẫn giữ nguyên nghĩa thời điểm/ngày từ
nguồn. `created_at` là lần insert đầu tiên và không bị reset khi conflict;
`updated_at`, `fetched_at`, `received_at`, `last_updated_at` ghi nhận hành động app
tương ứng gần nhất. Migration loại bỏ default theo clock DB; pipeline bắt buộc gửi các field này.
