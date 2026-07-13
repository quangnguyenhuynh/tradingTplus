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