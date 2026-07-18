# Data Pipeline

## 1. Mục đích

Tài liệu này mô tả luồng dữ liệu đang chạy trong repository Trading T+ và các nguyên tắc bắt buộc khi phát triển tiếp.

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

Pipeline không tự động nối ingest sang feature, signal hoặc backtest.

---

## 2. Nguyên tắc kiến trúc

### 2.1 Tách các tầng xử lý

Các tầng độc lập:

1. Master data.
2. Raw ingest.
3. Clean data.
4. Validation và completeness.
5. Feature.
6. Signal.
7. Backtest.
8. Alert.

Một tầng không tự động chạy tầng tiếp theo nếu command hiện tại không yêu cầu.

### 2.2 Daily và intraday tách biệt

- Daily là bối cảnh chính cho T+3 đến T+5.
- Intraday dùng cho xác nhận và timing.
- Không tính canonical feature `1d` từ intraday.
- Không dùng vài indicator `1m` làm cơ sở chính cho quyết định T+3/T+5.

### 2.3 Raw và clean tách biệt

- Raw data phục vụ đối chiếu nguồn, debug và remap/backfill khi đủ lineage.
- Clean data phục vụ validation, feature và research.
- Clean data phải được tạo từ source record qua mapper rõ ràng.
- Không tạo dữ liệu giả cho ngày nghỉ, cuối tuần, API rỗng hoặc endpoint không hỗ trợ.

### 2.4 Feature chạy riêng

Feature pipeline phải hỗ trợ:

- rerun;
- incremental;
- target date;
- historical backfill;
- idempotent upsert.

---

## 3. Tổng quan pipeline hiện tại

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
        │     ├── foreign_trading
        │     └── index_daily
        │
        ├── Intraday ingest pipeline
        │     ├── raw_intraday
        │     └── stock_intraday 1m
        │
        └── Streaming/snapshot pipeline
              ├── stream_raw_snapshot
              ├── stream_quote_snapshot
              ├── stream_trade_snapshot
              ├── stream_foreign_snapshot
              ├── stream_index_snapshot
              ├── stream_status_snapshot
              ├── stream_bar_snapshot
              └── orderbook_snapshot utilities

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
          └── alert job riêng trong phase sau
```

---

## 4. Production command responsibilities

### `sync-master-data` / `init`

- Đồng bộ symbols, securities, indexes và index components.
- Không ingest history hoặc tính feature.

### `daily`

- Một `DailyStockPrice` request mỗi symbol/date được reuse cho `raw_daily`, `stock_daily` và foreign fields.
- `DailyIndex` ghi `index_daily`.
- Không gọi `IntradayOhlc`.
- Không tính feature/signal/backtest.

### `intraday-ingest`

- Gọi SSI `IntradayOhlc` resolution `1`.
- Ghi `raw_intraday` và `stock_intraday` với `timeframe='1m'`.
- Có thể đọc optional `stock_daily` context.
- Không gọi `DailyStockPrice` hoặc ghi daily tables.
- Không tính feature/signal/backtest.

### `eod`

```text
daily
→ intraday-ingest
→ completeness check
```

EOD không chạy feature.

### `features`

- Pipeline feature production duy nhất.
- Chạy explicit theo mode/date/symbol/timeframe.
- `1d` lấy từ `stock_daily`.
- Intraday timeframe cao hơn aggregate từ clean 1m.

### `intraday`

- Legacy alias cho incremental intraday features trên dữ liệu đã ingest.
- Không lấy SSI candle mới.

### `streaming-ingest`

- Tách khỏi historical ingest.
- Chỉ subscribe explicit symbols/indexes/channels.
- Bounded timeout/message limit.
- Dry-run mặc định; chỉ ghi khi có `--write`.
- Raw audit records tách khỏi clean streaming snapshots.
- Realtime bar `B` không phải canonical `stock_intraday`.

---

## 5. Data contracts

### Daily

```text
DailyStockPrice
    ├── raw_daily
    ├── stock_daily
    └── foreign_trading

DailyIndex
    └── index_daily
```

`DailyOhlc` chỉ dùng inspector/cross-check.

### Intraday

```text
IntradayOhlc resolution=1
    ├── raw_intraday
    └── stock_intraday timeframe=1m
```

`raw_intraday` hiện chưa giữ full source candle JSON. Đây là khoảng thiếu lineage cần quyết định bằng task schema riêng.

### Feature

```text
stock_daily → features 1d
stock_intraday 1m → features 1m/5m/15m/60m
```

Tất cả timeframe nằm trong một bảng `features` với key `(symbol, timeframe, time)`.

### Streaming

Raw stream giữ payload, receive time và validation status/issues. Clean stream được tách theo channel type và chỉ ghi record valid khi write được bật.

---

## 6. Validation và completeness

- Daily validation quyết định việc ghi `stock_daily` nhưng không tự động chặn pipeline intraday riêng.
- Intraday thiếu daily context vẫn có thể ingest; optional price-limit fields giữ `NULL`.
- Timestamp intraday lỗi bị bỏ qua, không thay bằng current time.
- Completeness kiểm tra daily/intraday presence, duplicate và missing intervals theo symbol/date.
- Index, foreign và orderbook counts được query nhưng chưa ảnh hưởng đầy đủ đến overall status.
- Không hardcode `226` candle làm chuẩn universal.
- Weekday-based date handling chưa thay thế exchange holiday calendar.

---

## 7. Downstream boundaries

Signal và backtest hiện là code MVP/research:

- không tự chạy sau ingest hoặc feature;
- không sửa raw/clean data;
- không được dùng để kết luận lợi nhuận;
- phải redesign sau khi Phase 0 data/feature có evidence.

Chi tiết trạng thái và known issues xem [CURRENT_STATE.md](CURRENT_STATE.md).
