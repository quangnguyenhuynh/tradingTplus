# Data Pipeline

## 1. Mục đích

Tài liệu này mô tả **luồng dữ liệu đang chạy trong repository Trading T+** và các nguyên tắc bắt buộc khi phát triển tiếp.

Project đang ở **Phase 0: xây dựng và kiểm chứng dữ liệu**.

Thứ tự ưu tiên:

1. Hiểu đúng dữ liệu và API SSI.
2. Lưu raw data có thể truy vết.
3. Chuẩn hóa clean data chính xác.
4. Kiểm tra completeness và consistency.
5. Tính feature có thể rerun và backfill.
6. Signal.
7. Backtest.
8. Tối ưu chiến lược và AI.

Pipeline hiện tại không tự động nối tiếp từ ingest sang feature, signal hoặc backtest.

---

## 2. Nguyên tắc kiến trúc

### 2.1 Tách các tầng xử lý

Các tầng sau phải độc lập:

1. Master data
2. Raw ingest
3. Clean data
4. Validation và completeness
5. Feature
6. Signal
7. Backtest
8. Alert

Một tầng không được tự động chạy tầng tiếp theo nếu command hiện tại không yêu cầu.

### 2.2 Daily và intraday tách biệt

- Daily dùng cho bối cảnh chính của T+3 đến T+5.
- Intraday dùng cho xác nhận và timing.
- Không tính feature `1d` từ intraday.
- Không dùng vài indicator `1m` làm cơ sở chính cho quyết định T+3/T+5.

### 2.3 Raw và clean tách biệt

- Raw data phục vụ đối chiếu nguồn, debug và backfill.
- Clean data phục vụ validation, feature và nghiên cứu.
- Clean data phải được tạo từ source record thông qua mapper rõ ràng.
- Không tạo dữ liệu giả cho ngày nghỉ, cuối tuần, API rỗng hoặc endpoint không hỗ trợ.

### 2.4 Feature chạy riêng

Ingest không tự động tính feature.

Feature pipeline phải hỗ trợ:

- rerun;
- incremental;
- target date;
- historical backfill;
- idempotent upsert.

---

## 3. Tổng quan pipeline

```text
SSI FastConnect Data
        │
        ├── Master-data pipeline
        │     ├── symbols
        │     ├── securities
        │     ├── indexes
        │     └── index_components
        │
        ├── Daily ingest pipeline
        │     ├── raw_daily
        │     ├── stock_daily
        │     ├── raw_intraday
        │     ├── stock_intraday 1m
        │     ├── foreign_trading
        │     └── index_daily
        │
        └── Streaming / snapshot pipeline
              └── orderbook_snapshot và các snapshot khác

stock_daily
    └── feature 1d

stock_intraday 1m
    ├── feature 1m
    ├── aggregate 5m  → feature 5m
    ├── aggregate 15m → feature 15m
    └── aggregate 60m → feature 60m

Tất cả feature
    └── features
          ├── signal job riêng
          ├── backtest job riêng
          └── alert job riêng
---

## Phase 0 production commands after daily/intraday split

Production ingest responsibilities are explicit:

- `daily` ingests daily source data only: `DailyStockPrice` to `raw_daily`/`stock_daily`, foreign fields to `foreign_trading`, and `DailyIndex` to `index_daily`.
- `intraday-ingest` ingests SSI `IntradayOhlc` resolution `1` only, writing `raw_intraday` and `stock_intraday` with persisted `timeframe='1m'`.
- `eod` orchestrates `daily` → `intraday-ingest` → completeness check.
- `features` is the only production feature pipeline and is run explicitly.
- `intraday` remains a legacy feature alias for existing intraday data and does not ingest SSI candles.

Intraday ingest may read optional `stock_daily` context for validation of the same `symbol + trading_date`, but it must not call `DailyStockPrice` or write daily tables. Missing context is reported and optional price-limit fields remain `NULL`/`None`, not zero.

`stock_daily` is the canonical source for `1d` features. `stock_intraday` stores only clean 1-minute candles; higher intraday feature timeframes are aggregated by the feature pipeline and are not persisted back into `stock_intraday`.
