# Data pipelines

Orchestration production cho master data, daily/intraday ingest, EOD validation, compatibility feature, backfill và snapshot có giới hạn.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Luồng chính

| File/flow | Trách nhiệm hiện tại |
| --- | --- |
| `init_symbols.py` | Đồng bộ symbols, securities, indexes và index components. |
| `daily.py` | Chỉ ingest daily SSI: `raw_daily`, `stock_daily`, foreign fields và `index_daily`. |
| `intraday_ingest.py` | Ghi `IntradayOhlc` resolution 1 vào `raw_intraday` và `stock_intraday`. |
| `eod.py` | Daily ingest → intraday ingest → completeness check. |
| `fetch_one_day.py` | Helper mapping theo đúng một symbol/date. |
| `ingest_check.py` | Summary completeness và báo dữ liệu thiếu. |
| `date_utils.py` | Parse ngày theo thị trường Việt Nam và kiểm tra write an toàn. |
| `foreign_trading.py` | Derive foreign trading từ field `DailyStockPrice`. |
| `index_data.py` | Ingest index master và daily index. |
| `backfill.py` | Ingest lịch sử có phạm vi rõ ràng. |
| `intraday.py` | Compatibility flow tính intraday feature; không ingest candle. |
| `streaming_snapshot.py` | Thu streaming có giới hạn; read-only nếu chưa bật write. |
| `orderbook_snapshot.py` | Mapping orderbook snapshot từ quote stream. |
| `eod_dry_run.py` | Kiểm tra EOD read-only. |

## Tách biệt bắt buộc

```text
daily ingest ─┐
              ├─> EOD completeness khi cần orchestration
intraday ingest┘

validated clean data ─> feature pipeline chạy riêng
features ─> signal/backtest job riêng khi được yêu cầu
```

## Quy tắc dữ liệu

- Nguồn daily chuẩn: SSI `DailyStockPrice` → `stock_daily`.
- `DailyOhlc` chỉ để inspector/đối chiếu, không thuộc production daily ingest.
- Intraday chỉ lưu timeframe `1m`.
- Foreign trading derive từ field `DailyStockPrice`; không tự tạo public REST endpoint riêng.
- Orderbook lấy từ quote streaming được hỗ trợ hoặc private endpoint cấu hình rõ; unsupported phải báo, không tạo giả.
- Không hardcode một số candle làm chuẩn completeness cho mọi ngày.

## Lỗi và thao tác ghi

Retry phải giới hạn, log đủ symbol/date/timeframe/endpoint, loại timestamp sai và không nuốt exception. Luồng ghi cần phạm vi rõ ràng và conflict key idempotent.

## Test

Test liên quan gồm CLI, daily/EOD, one-day mapping, intraday ingest, streaming ingest, completeness và dry-run trong `tests/`.
