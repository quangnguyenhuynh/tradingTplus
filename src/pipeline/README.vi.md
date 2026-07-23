# Data pipelines

[English](README.md) | [Tiếng Việt](README.vi.md)

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
├── backfill.py               # orchestration khoảng ngày, mỗi ngày trong tuần gọi EOD
├── ingest_check.py           # báo cáo completeness/consistency
├── date_utils.py             # parse/kiểm tra ngày thị trường Việt Nam
├── init_symbols.py           # đồng bộ master data
├── index_data.py             # ingest index master/daily
├── foreign_trading.py        # writer compatibility legacy explicit; không thuộc daily ingest thường
├── intraday.py               # alias feature legacy, không ingest candle
├── eod_dry_run.py            # utility preview EOD/feature read-only
├── streaming_snapshot.py     # streaming capture có giới hạn
└── orderbook_snapshot.py     # mapping orderbook từ quote stream
```

Các module streaming, index, master data, compatibility feature và dry-run vẫn tách khỏi daily/intraday REST ingest.

## Trình tự daily

Public entrypoint: `daily_run()` / `run_daily_ingest()` trong `daily.py`; CLI `python main.py daily [DD/MM/YYYY]`.

1. Resolve và validate ngày theo thị trường Việt Nam.
2. `daily_fetcher.py` gọi SSI `DailyStockPrice` đúng một lần cho mỗi mã.
3. `daily_mapper.py` tạo record giữ payload nguồn cho `raw_daily` và candidate chuẩn hóa cho `stock_daily`; field thiếu giữ `None`.
4. `daily_service.py` ghi raw evidence qua `daily_persistence.py`.
5. `daily_service.py` gọi validator `validate_daily_record` hiện có.
6. Chỉ clean candidate hợp lệ mới được ghi vào `stock_daily` qua `daily_persistence.py`.
7. Các field mua, bán, net và room khối ngoại cuối ngày nằm trong row `stock_daily`; daily ingest thông thường không ghi `foreign_trading`.
8. `daily.py` xử lý index độc lập.

`stock_daily` là nguồn canonical cho dữ liệu daily, bao gồm dữ liệu giao dịch khối ngoại và room cuối ngày. `foreign_trading` là bảng legacy và không còn được daily ingest ghi dữ liệu mới; helper compatibility explicit vẫn được giữ lại. Snapshot khối ngoại intraday vẫn là streaming dataset riêng.

## Trình tự intraday

Public entrypoint: `run_intraday_ingest()` trong `intraday_ingest.py`; CLI `python main.py intraday-ingest [DD/MM/YYYY] [--symbols ...]`.

1. Resolve ngày và scope symbol explicit hoặc active.
2. Đọc daily context tùy chọn từ `stock_daily`; bước này không fetch hay ghi daily.
3. `intraday_fetcher.py` gọi SSI `IntradayOhlc` resolution 1.
4. `intraday_mapper.py` hiểu timestamp nguồn theo `Asia/Ho_Chi_Minh`, đổi sang UTC, loại timestamp sai và tạo raw/clean candidate.
5. Mapper chỉ tạo `timeframe='1m'`; `value` là ước tính `round(close * volume)` và giữ `None` nếu đầu vào thiếu/sai.
6. `intraday_service.py` ghi raw evidence qua `intraday_persistence.py`, gọi validator record/batch hiện có, deduplicate theo `(symbol,timeframe,time)` khi validator báo trùng, rồi ghi clean hợp lệ.

Timeframe intraday cao hơn chỉ được aggregate trong feature pipeline và không ghi vào `stock_intraday`.

Validation gap intraday chỉ chuẩn hóa timestamp thành minute bucket trong bộ nhớ; timestamp raw và clean không bị thay đổi. Bucket trống/thiếu chỉ được kiểm tra trong các đoạn khớp lệnh liên tục `09:00-11:29` và `13:00-14:29` (`Asia/Ho_Chi_Minh`). Các phút nghỉ trưa và khoảng ATC `14:30-14:44` trước kết quả đóng cửa SSI vào khoảng `14:45` bị loại khỏi phép đếm. Validator sort nội bộ để kiểm tra gap nhưng vẫn báo rõ input không sort.

`INTRADAY_MISSING_INTERVAL` có nghĩa là **minute bucket trống/thiếu quan sát được**. Chỉ từ IntradayOhlc không thể phân biệt phút không có giao dịch với source omission. Vì vậy gap ngắn, rời rạc vẫn được đếm trong `missing_interval_count`, `missing_minutes` và `empty_minute_bucket_count`, nhưng tự nó không làm completeness fail và không tạo candle giả. Duplicate và mất coverage có tính cấu trúc vẫn tạo `WARNING`/`PARTIAL`. Heuristic ban đầu là ngưỡng data-quality minh bạch, không phải quy tắc SSI chính thức: gap liên tục ít nhất 15 phút, tổng ít nhất 30 phút trống, thiếu phiên sáng/chiều, hoặc first/last coverage lệch vào trong quá 15 phút. Không dùng một candle count cố định chung.

## Trình tự EOD

Public entrypoint: `run_eod_pipeline()` trong `eod.py`; CLI `python main.py eod [DD/MM/YYYY]`.

```text
daily ingest -> intraday ingest -> kiểm tra completeness -> OK/PARTIAL/FAILED
```

EOD giữ nguyên ranh giới daily/intraday. EOD không tính feature, không chạy signal và không chạy backtest.

## Trình tự backfill

Public entrypoint: `run_backfill_pipeline()` trong `backfill.py`; CLI:

```bash
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY
```

Backfill validate khoảng lịch sử bao gồm cả ngày đầu/cuối, bỏ thứ Bảy và Chủ nhật, sau đó gọi `run_eod_pipeline()` cho từng ngày còn lại. Summary của từng ngày được giữ nguyên và summary toàn khoảng đếm số ngày `OK`, `PARTIAL`, `FAILED`. Backfill không nhân đôi code ingest và không chạy feature, signal hay backtest.

Backfill hiện dùng cùng toàn bộ danh sách mã active như EOD; chưa mở scope theo symbol. Ngày trong tuần chỉ là ứng viên theo lịch, vì vậy ngày lễ hoặc SSI trả rỗng sẽ được EOD báo đúng trạng thái và không bao giờ được thay bằng dữ liệu giả.

Tài liệu đầy đủ: [`docs/backfill/README.vi.md`](../../docs/backfill/README.vi.md).

## Raw, clean, validation và persistence

| Dataset | Tạo record | Tích hợp validation | Ghi dữ liệu |
| --- | --- | --- | --- |
| `raw_daily` | `daily_mapper.py` | giữ raw evidence trước clean validation | `daily_persistence.py` |
| `stock_daily` | `daily_mapper.py` | `daily_service.py` + daily validator hiện có | `daily_persistence.py` |
| `raw_intraday` | `intraday_mapper.py` | giữ raw evidence trước clean validation | `intraday_persistence.py` |
| `stock_intraday` | `intraday_mapper.py` | `intraday_service.py` + intraday validator hiện có | `intraday_persistence.py` |

## Compatibility wrapper

`fetch_one_day.py` được giữ làm compatibility module mỏng cho import cũ và script có scope rõ. File re-export helper fetcher/mapper legacy và compose daily/intraday service public; không còn implementation mapping, validation hay persistence trùng lặp. Code mới phải import module theo tầng tương ứng.

Tên hàm legacy `backfill()` vẫn được giữ làm wrapper quanh `run_backfill_pipeline()`. Python function vẫn nhận chuỗi ngày ISO cũ, nhưng từ chối backfill theo symbol và ngày tương lai vì không thuộc contract EOD production. `scripts/backfill_sample.py` đã deprecated và chỉ gọi lại pipeline backfill chính.

## Error và retry

- Fetcher trả kết quả SSI và không nuốt lỗi service/DB.
- Response SSI rỗng không tạo raw/clean giả.
- Timestamp sai bị loại, không thay bằng thời gian hiện tại.
- Service gắn context symbol/date và giữ summary contract hiện có.
- Retry HTTP có giới hạn vẫn thuộc `src/ssi/api.py`; retry/backoff DB có giới hạn vẫn thuộc `src/database/client.py`.
- Persistence tiếp tục dùng DB public methods và conflict keys hiện có.
- Backfill bắt lỗi tại ranh giới từng ngày, ghi ngày/lỗi vào summary toàn khoảng và tiếp tục ngày sau; EOD summary lỗi không bị che mất.

## Chạy test

```bash
python -m pytest -q tests/ingest/test_fetch_one_day.py
python -m pytest -q tests/ingest/test_intraday_ingest_pipeline.py
python -m pytest -q tests/validation/test_intraday_validator.py
python -m pytest -q tests/ingest/test_ingest_check.py
python -m pytest -q tests/pipeline/test_eod_pipeline.py
python -m pytest -q tests/pipeline/test_backfill_pipeline.py
python -m pytest -q tests/cli/test_cli_refactor.py
python -m pytest -q
```

Ingest và backfill không bao giờ tự tính feature, sinh signal hoặc chạy backtest. Các bước downstream này chỉ chạy bằng command explicit.
