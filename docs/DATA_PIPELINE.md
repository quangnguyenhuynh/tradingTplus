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

Trong mỗi REST ingest pipeline, trách nhiệm được tách theo module: fetcher chỉ gọi SSI; mapper chỉ tạo raw/clean candidate; service tích hợp validator hiện có; persistence chỉ gọi DB public methods; batch orchestrator điều phối phạm vi symbol/date. Daily và intraday không import private helper của nhau. `src/pipeline/fetch_one_day.py` chỉ còn là compatibility wrapper mỏng; cấu trúc file đầy đủ nằm tại [`src/pipeline/README.vi.md`](../src/pipeline/README.vi.md).

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
        │     ├── stock_raw_daily
        │     ├── stock_daily (bao gồm foreign daily/room)
        │     └── index_daily
        │
        ├── Intraday ingest pipeline
        │     ├── stock_raw_intraday
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
              └── stock_orderbook_snapshot utilities

stock_daily
    └── feature 1d

stock_intraday 1m
    ├── aggregate 15m → feature 15m
    └── aggregate 60m → feature 60m

Feature 1m/5m không được persist trong production.

Tất cả feature
    └── features
          ├── signal job riêng
          ├── backtest job riêng
          └── alert job riêng trong phase sau
```

---

## 4. Production command responsibilities

### `sync-master-data` / `init`

- Đọc SSI `Securities`, `SecuritiesDetails`, `IndexList` và `IndexComponents`.
- Ghi `symbols`, `securities`, `index_master` và `index_components`.
- Không ingest history hoặc tính feature.

### `daily`

- Một `DailyStockPrice` request mỗi symbol/date được reuse cho `stock_raw_daily`, `stock_daily` và foreign fields.
- Chỉ gọi `DailyStockPrice`; không gọi `DailyIndex`, `IndexList` hoặc `IndexComponents`.
- Chỉ ghi `stock_raw_daily`, `stock_daily`; không ghi `index_daily`, `index_master` hoặc `index_components`.
- Không gọi `IntradayOhlc`.
- Không tính feature/signal/backtest.

### `intraday-ingest`

- Gọi SSI `IntradayOhlc` resolution `1`.
- Ghi `stock_raw_intraday` và `stock_intraday` với `timeframe='1m'`.
- Có thể đọc optional `stock_daily` context.
- Chỉ đọc SSI `IntradayOhlc` resolution `1`; daily context đến từ database, không được fetch lại từ SSI.
- Không gọi `DailyStockPrice` hoặc ghi daily tables.
- Không tính feature/signal/backtest.

### `eod`

```text
daily
→ intraday-ingest
→ completeness check
```

EOD không chạy feature.

### `stock_features`

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
    ├── stock_raw_daily
    └── stock_daily (canonical, bao gồm foreign daily/room)

`DailyIndex`/`index_daily` không thuộc daily, EOD hoặc backfill stock-only. Schema và dữ liệu index cũ vẫn được giữ nguyên.
```

`DailyOhlc` chỉ dùng inspector/cross-check.

Normal daily ingest không ghi `stock_foreign_trading`; bảng này chỉ còn là legacy historical storage. Intraday foreign snapshot vẫn thuộc streaming pipeline riêng.

### Intraday

```text
IntradayOhlc resolution=1
    ├── stock_raw_intraday
    └── stock_intraday timeframe=1m
```

Sau migration `20260803_add_raw_intraday_payload.sql`, ingest mới giữ toàn bộ
object candle SSI theo ngữ nghĩa JSON trong `stock_raw_intraday.payload JSONB` nullable.
Row lịch sử có thể `NULL`; pipeline không dựng payload giả hoặc backfill, và
`stock_intraday` clean không chứa payload này.

### Feature

```text
stock_daily → features 1d
stock_intraday 1m → aggregate trong feature pipeline → features 15m/60m
```

Tất cả timeframe nằm trong một bảng `stock_features` với key `(symbol, timeframe, time)`.
Production chỉ persist `1d`, `15m`, `60m`; `1m` là timeframe nguồn clean và
feature `1m`/`5m` bị public runner từ chối.

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

Runtime rule cũ đã bị xóa. Historical Analog EOD V1 đã có schema, pipeline và
CLI active. Ingest không tự chạy feature; feature không tự chạy Analog, signal,
backtest hoặc alert.

Chi tiết trạng thái và known issues xem [CURRENT_STATE.md](CURRENT_STATE.md).
# Write timestamp contract

At each persistence boundary, the application uses one timezone-aware `Asia/Ho_Chi_Minh` clock with an explicit `+07:00` offset for the logical write. Source candle/snapshot `time`, `source_time`, and
`trading_date` are never replaced by that value. New rows receive `created_at`;
conflict updates omit it so reruns/backfills preserve the first insert time.
Mutable source rows receive `updated_at`, raw fetches receive `fetched_at`, stream
messages retain app `received_at`, and feature rows receive `last_updated_at`. Database
clock defaults are removed for these fields, so writers must send them explicitly.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.

## Canonical DailyIndex pipeline

`SSI DailyIndex -> index_raw_daily -> validation -> index_daily -> index completeness` is a separate source-data flow. Index definitions live in `index_master`; constituents remain in `index_components`. Raw payloads use `(index_code, trading_date, data_hash)` and clean rows use `(index_code, trading_date)`. A payload outside requested code/date scope is retained raw and rejected from clean storage. Historical repair uses the explicit `index-backfill` command.
