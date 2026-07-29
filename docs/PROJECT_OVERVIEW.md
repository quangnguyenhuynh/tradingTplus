# Project Overview

## Project Name

**Trading T+**

Trading T+ là hệ thống thu thập, kiểm tra và phân tích dữ liệu chứng khoán Việt Nam, hướng đến việc hỗ trợ giao dịch với thời gian nắm giữ khoảng **T+3 đến T+5 phiên**.

Repository hiện tại tập trung vào backend dữ liệu bằng Python. Ứng dụng hiển thị, cảnh báo và giao diện người dùng sẽ được phát triển sau khi nền tảng dữ liệu đủ tin cậy.

---

## Product Goal

Mục tiêu dài hạn của Trading T+ là:

- Phân tích cổ phiếu Việt Nam cho giao dịch T+3 đến T+5 phiên.
- Đánh giá xu hướng, động lượng, thanh khoản và bối cảnh thị trường.
- Kết hợp daily context với intraday confirmation.
- Tạo signal có lý do rõ ràng.
- Ước tính confidence hoặc xác suất của signal.
- Gợi ý phạm vi phần trăm NAV phù hợp với mức rủi ro.
- Backtest signal trên dữ liệu lịch sử.
- Cảnh báo tại các thời điểm chọn trước như:
  - `09:30`;
  - `11:30`;
  - `13:30`;
  - `14:30`.

Hệ thống phải ưu tiên:

- ít cảnh báo;
- dễ giải thích;
- không spam;
- không tự động đưa ra kết luận sinh lợi khi dữ liệu chưa được kiểm chứng.

Trading T+ không nhằm trở thành hệ thống giao dịch tần suất cao hoặc tự động mua bán hoàn toàn.

---

## Problem Being Solved

Dữ liệu thị trường chứng khoán có thể gặp nhiều vấn đề trước khi được dùng để tính indicator, signal hoặc backtest:

- API trả response rỗng.
- Response không đúng symbol hoặc trading date được yêu cầu.
- Timestamp sai hoặc không parse được.
- Thiếu candle intraday.
- Duplicate candle.
- Volume hoặc value có cách hiểu không rõ ràng.
- Daily và intraday không khớp nhau.
- Ngày nghỉ hoặc cuối tuần bị hiểu nhầm là ngày có giao dịch.
- Field từ API và schema database không đồng nhất.
- Feature incremental và full run có thể cho kết quả khác nhau.
- Backtest có thể bị look-ahead nếu pipeline không được tách đúng.

Nếu dữ liệu đầu vào không chính xác thì:

- indicator không đáng tin;
- signal không đáng tin;
- backtest không có ý nghĩa;
- tối ưu chiến lược hoặc AI có thể học từ dữ liệu sai.

Trading T+ giải quyết vấn đề này bằng cách xây dựng pipeline theo thứ tự:

```text
SSI source
    ↓
Raw data
    ↓
Clean data
    ↓
Validation và completeness
    ↓
Features
    ↓
Signals
    ↓
Backtest
    ↓
Alerts
```

Không được bỏ qua các bước kiểm chứng dữ liệu để đi thẳng đến signal hoặc tối ưu lợi nhuận.

---

## Target Users

### Người dùng hiện tại

Trong Phase 0, hệ thống chủ yếu phục vụ:

- project owner;
- developer;
- data engineer;
- người kiểm tra dữ liệu SSI;
- người nghiên cứu chiến lược T+.

### Người dùng tương lai

Khi hệ thống đủ ổn định, sản phẩm có thể phục vụ:

- nhà đầu tư cá nhân trên thị trường chứng khoán Việt Nam;
- người giao dịch ngắn hạn theo T+3 đến T+5;
- người cần signal có giải thích thay vì chỉ có lệnh mua/bán;
- người muốn theo dõi một danh sách cổ phiếu mà không nhận quá nhiều cảnh báo.

Hệ thống không thay thế tư vấn tài chính chuyên nghiệp và không bảo đảm lợi nhuận.

---

## Main Use Cases

## 1. Đồng bộ master data

Hệ thống đồng bộ:

- danh sách mã chứng khoán;
- thông tin chi tiết chứng khoán;
- danh sách chỉ số;
- thành phần chỉ số.

Command chính:

```bash
python main.py sync-master-data
```

Alias tương thích:

```bash
python main.py init
```

---

## 2. Ingest dữ liệu theo ngày

Hệ thống lấy dữ liệu SSI cho một trading date và ghi vào các tầng raw và clean.

Command:

```bash
python main.py daily DD/MM/YYYY
```

Daily ingest hiện xử lý:

- `DailyStockPrice`;
- foreign trading fields từ `DailyStockPrice`;
- `DailyIndex`;
- master index data cần thiết.

Daily ingest không tự động tính:

- feature;
- signal;
- backtest;
- recommendation.

---

## 3. EOD ingest và completeness check

Command:

```bash
python main.py eod DD/MM/YYYY
```

EOD hiện chạy:

```text
daily ingest
    ↓
intraday ingest 1m
    ↓
ingest completeness check
    ↓
OK / PARTIAL / FAILED
```

EOD dừng sau validation và completeness.

EOD không tự động chạy feature, signal hoặc backtest.

---

## 4. Kiểm tra dữ liệu

Hệ thống kiểm tra:

- daily record hợp lệ;
- OHLC hợp lệ;
- giá nằm trong floor/ceiling;
- volume/value không âm;
- timestamp intraday hợp lệ;
- duplicate candle;
- missing interval;
- candle ngoài trading session;
- daily close so với intraday close;
- daily volume so với tổng intraday volume;
- symbol nào thiếu daily;
- symbol nào thiếu intraday.

Command kiểm tra riêng:

```bash
python scripts/check_ingest.py --date DD/MM/YYYY
```

Completeness phải được đánh giá theo:

- symbol;
- trading date;
- source;
- timeframe;
- trading session.

Không dùng một con số cố định như `226` candle để kết luận mọi ngày đều đầy đủ.

---

## 5. Tính feature

Feature chạy bằng pipeline riêng:

```bash
python main.py features \
  --mode incremental \
  --date DD/MM/YYYY \
  --symbols SSI HPG \
  --timeframes 1m 5m 15m 60m 1d
```

Feature pipeline hỗ trợ:

- incremental;
- full;
- target date;
- symbol scope;
- timeframe scope;
- rerun;
- backfill.

Nguồn feature:

| Timeframe | Nguồn |
|---|---|
| `1d` | `stock_daily` |
| `1m` | `stock_intraday` |
| `5m` | aggregate từ `stock_intraday` 1m |
| `15m` | aggregate từ `stock_intraday` 1m |
| `60m` | aggregate từ `stock_intraday` 1m |

Tất cả feature được lưu vào một bảng:

```text
features
```

Key chính:

```text
symbol,timeframe,time
```

Không tự ý tách bảng feature theo timeframe.

---

## 6. Backfill dữ liệu

Ingest backfill phải có phạm vi symbol và date rõ ràng.

Ví dụ:

```bash
python scripts/backfill_sample.py \
  --from-date 2026-07-01 \
  --to-date 2026-07-10 \
  --symbols SSI HPG
```

Backfill ingest không tự động chạy feature.

Sau khi ingest và completeness đạt yêu cầu, feature được chạy riêng cho các ngày cần backfill.

---

## 7. Intraday confirmation

Trong sản phẩm tương lai, intraday data được dùng để:

- xác nhận daily setup;
- chọn thời điểm vào;
- nhận biết tăng tốc hoặc suy yếu trong phiên;
- tạo snapshot tại các mốc cảnh báo.

Vai trò timeframe:

- `1d`: bối cảnh chính cho T+3/T+5;
- `60m`, `15m`: xác nhận và chọn thời điểm;
- `5m`, `1m`: timing ngắn hạn và snapshot.

Command hiện tại:

```bash
python main.py intraday --symbols SSI HPG
```

Đây là legacy alias cho incremental intraday feature calculation.

Command này hiện:

- không gọi SSI để ingest candle mới;
- chỉ đọc dữ liệu đã có trong `stock_intraday`;
- mặc định tính feature `1m`, `5m`, `15m`;
- không tính `1d`.

---

## 8. Signal, backtest và alert

Đây là mục tiêu của các phase sau.

Flow dự kiến:

```text
validated data
    ↓
features
    ↓
explicit signal job
    ↓
explicit backtest job
    ↓
strategy review
    ↓
alert
```

Signal, backtest và alert không tự động chạy sau ingest hoặc feature nếu task không yêu cầu.

---

## Main Components

## 1. CLI entrypoint

File:

```text
main.py
```

Vai trò:

- nhận command;
- parse argument;
- gọi production pipeline;
- in summary;
- trả exit code.

Production commands hiện có:

- `sync-master-data`;
- `init`;
- `daily`;
- `eod`;
- `features`;
- `intraday`.

---

## 2. SSI integration

Thư mục:

```text
src/ssi/
```

Vai trò:

- đăng nhập SSI;
- quản lý access token;
- gọi SSI REST API;
- retry một lần khi gặp HTTP `401`;
- phân trang response;
- hỗ trợ SSI streaming khi được cấu hình.

Không được tự tạo endpoint hoặc field SSI không có trong tài liệu hoặc API thực tế.

---

## 3. Data pipelines

Thư mục:

```text
src/pipeline/
```

Bao gồm các flow chính:

- master-data sync;
- daily ingest;
- EOD orchestration;
- one-day ingest;
- foreign trading;
- index data;
- completeness check;
- backfill;
- intraday compatibility flow;
- streaming và snapshot khi được hỗ trợ.

---

## 4. Validation layer

Thư mục:

```text
src/validation/
```

Vai trò:

- validate daily clean record;
- validate intraday clean record;
- validate intraday batch;
- phân biệt error và warning;
- ngăn clean data lỗi được ghi vào database;
- hỗ trợ summary và logging.

Validation phải độc lập với feature, signal và backtest.

---

## 5. Database layer

Thư mục:

```text
src/database/
```

Database hiện sử dụng Supabase PostgreSQL.

Vai trò:

- kết nối Supabase;
- batch upsert;
- bounded retry;
- kiểm tra conflict key;
- tạo partition intraday theo tháng;
- chặn ghi timeframe khác `1m` vào `stock_intraday`;
- chặn feature columns bị ghi nhầm vào clean candle table.

Mọi thay đổi schema phải có migration.

---

## 6. Feature engine

Thư mục:

```text
src/engine/
```

Feature engine hiện:

- đọc `stock_daily` cho timeframe `1d`;
- đọc `stock_intraday` cho intraday;
- aggregate `1m` thành `5m`, `15m`, `60m`;
- hỗ trợ incremental và full mode;
- sử dụng warm-up history;
- upsert vào bảng `features`.

Các nhóm feature hiện có:

- OHLCV;
- returns;
- EMA;
- RSI;
- MACD;
- volume moving average;
- value moving average;
- volume/value ratio;
- rolling high/low;
- breakout flags;
- intraday VWAP;
- candle structure.

---

## 7. Scripts

Thư mục:

```text
scripts/
```

Dùng cho:

- smoke test;
- read-only inspection;
- schema check;
- completeness check;
- sample backfill;
- manual feature run;
- maintenance;
- debug SSI;
- streaming test.

Nguyên tắc:

- debug script mặc định read-only;
- write phải được yêu cầu rõ ràng;
- destructive operation phải giới hạn symbol/date.

---

## 8. Tests

Thư mục:

```text
tests/
```

Test bao phủ các nhóm như:

- CLI;
- EOD pipeline;
- daily ingest;
- mapper;
- feature engine;
- feature calculator;
- daily validator;
- intraday validator;
- database behavior;
- intraday value;
- signal/backtest MVP khi có liên quan.

Không báo task hoàn thành nếu chưa chạy test phù hợp.

---

## 9. Migrations và schema

Các thành phần liên quan:

```text
schema.sql
migrations/
docs_db_schema.md
```

Vai trò:

- định nghĩa database contract;
- thêm bảng, cột và unique index;
- giữ code và database đồng nhất;
- hỗ trợ Supabase deployment.

Không thay đổi schema trực tiếp mà không có migration.

---

## Technology Stack

### Backend

- Python 3
- `requests`
- `pandas`
- `numpy`

### Data source

- SSI FastConnect Data REST API
- SSI FastConnect streaming khi được hỗ trợ
- `DailyStockPrice`
- `IntradayOhlc`
- `DailyIndex`
- `Securities`
- `SecuritiesDetails`
- `IndexList`
- `IndexComponents`

### Database

- Supabase
- PostgreSQL
- JSON/JSONB raw payload
- Unique indexes cho idempotent upsert
- Monthly partitioning cho `stock_intraday`

### Testing

- `pytest`
- compile checks
- CLI smoke tests
- read-only SSI/Supabase checks

### Version control và automation

- Git
- GitHub
- GitHub Actions

### Planned client layer

Sau Phase 0, có thể phát triển:

- Flutter mobile app;
- dashboard;
- alert delivery;
- portfolio/watchlist UI.

Client layer không phải ưu tiên của Phase 0.

---

## Current Development Phase

Project đang ở:

```text
Phase 0 — Data Foundation and Validation
```

Mục tiêu của Phase 0 là chứng minh rằng dữ liệu:

- đúng source;
- đúng symbol;
- đúng trading date;
- đúng timezone;
- đúng field meaning;
- không duplicate ngoài ý muốn;
- không có fake trading data;
- có thể kiểm tra completeness;
- có thể rerun;
- có thể backfill;
- tạo feature ổn định và không look-ahead.

### Hành vi pipeline hiện tại

#### `daily`

```text
SSI ingest → raw data → validation → clean data
```

Dừng sau ingest.

#### `eod`

```text
daily ingest → intraday ingest → completeness check
```

Dừng sau completeness.

#### `features`

```text
validated clean data → feature computation → features table
```

Được gọi riêng.

#### `intraday`

Legacy feature alias.

Không ingest candle mới từ SSI.

### Điều kiện để kết thúc Phase 0

Phase 0 chỉ nên được coi là hoàn thành khi:

- SSI source contracts đã được kiểm chứng;
- raw và clean data có thể đối chiếu;
- daily validation ổn định;
- intraday validation ổn định;
- completeness chạy theo symbol/date;
- trading-session rules đã được xác nhận;
- date và timezone handling chính xác;
- unique indexes khớp conflict keys;
- ingest rerun không tạo duplicate;
- backfill có phạm vi an toàn;
- incremental và full feature output tương đương trong phạm vi kiểm tra;
- test suite liên quan chạy ổn định;
- các data-quality issue quan trọng đã được ghi nhận và xử lý.

---

## Development Priorities

Thứ tự ưu tiên bắt buộc:

### Priority 1: SSI source correctness

- Xác nhận endpoint thật.
- Xác nhận field thật.
- Xác nhận units.
- Xác nhận volume là cumulative hay per-candle.
- Xác nhận timestamp là candle start hay candle end.
- Xác nhận symbol/date trong response.

### Priority 2: Raw data correctness

- Raw data có thể truy vết về source.
- Có data hash phù hợp.
- Không tạo fake raw record.
- Không mất field quan trọng.
- Xác định rõ khoảng thiếu của `raw_intraday`.

### Priority 3: Clean data correctness

- Mapper rõ ràng.
- Không tự đổi missing thành `0`.
- Daily và intraday dùng đúng nguồn.
- `stock_intraday` chỉ lưu `1m`.
- Intraday value được ghi nhận là giá trị ước tính.

### Priority 4: Validation và completeness

- Daily OHLC validation.
- Intraday OHLC validation.
- Duplicate detection.
- Missing interval detection.
- Daily/intraday consistency.
- Completeness theo symbol và date.
- Trading calendar và special session handling.

### Priority 5: Reproducible features

- `1d` lấy từ `stock_daily`.
- Intraday lấy từ `stock_intraday`.
- Aggregate đúng session.
- Không look-ahead.
- Có warm-up đủ.
- Incremental và full có thể so sánh.
- Có thể rerun và backfill.

### Priority 6: Signal

Chỉ bắt đầu sau khi source data và feature được xác nhận.

### Priority 7: Backtest

Chỉ bắt đầu sau khi signal contract rõ ràng và feature không look-ahead.

### Priority 8: Strategy optimization và AI

Chỉ bắt đầu sau khi:

- dữ liệu đủ lịch sử;
- backtest đáng tin;
- transaction cost rõ ràng;
- outcome labeling đúng;
- bias đã được đánh giá.

---

## Out of Scope

## Out of scope trong Phase 0

Các hạng mục sau không phải ưu tiên hiện tại:

- tối ưu win rate;
- tối ưu lợi nhuận;
- AI prediction;
- machine-learning ranking;
- tự động gợi ý phần trăm NAV;
- portfolio position engine;
- live order execution;
- tự động đặt lệnh;
- production alert scheduler;
- tối ưu signal rules;
- quảng cáo khả năng sinh lợi;
- xây UI hoàn chỉnh;
- chia nhỏ hoặc thiết kế lại bảng `features` khi không có task schema riêng;
- lưu các cột lag có thể tính lúc query hoặc backtest;
- xóa toàn bộ dữ liệu cũ để làm lại khi chưa chứng minh cần thiết;
- thay đổi schema không có migration;
- refactor ngoài phạm vi task.

Signal và backtest vẫn thuộc mục tiêu dài hạn của project, nhưng không được ưu tiên trước khi Phase 0 hoàn thành.

---

## Product Principles

### Data before strategy

Dữ liệu đúng quan trọng hơn signal đẹp hoặc backtest có lợi nhuận cao.

### Explainable before complex

Ưu tiên rule và feature dễ kiểm tra trước AI hoặc mô hình phức tạp.

### Few alerts, not spam

Chỉ cảnh báo ở các thời điểm có ý nghĩa và khi có đủ lý do.

### Daily context first

Quyết định T+3/T+5 phải dựa chủ yếu vào daily context.

Intraday chỉ hỗ trợ xác nhận và timing.

### Reproducible

Mỗi kết quả phải có thể tái tạo từ:

- source data;
- mapper;
- feature version;
- signal rule;
- backtest configuration.

### Safe operations

- Read-only mặc định cho debug.
- Write phải có phạm vi rõ ràng.
- Delete phải có guard.
- Retry phải giới hạn.
- Không in secret hoặc token.
- Không nuốt exception.

---

## Success Criteria

Project được xem là đi đúng hướng khi:

- Có thể lấy dữ liệu SSI ổn định.
- Raw và clean data tách biệt.
- Có thể kiểm tra dữ liệu của một symbol/date cụ thể.
- Có thể phát hiện missing, duplicate và mismatch.
- Ingest có thể rerun mà không tạo duplicate.
- Feature có thể incremental và backfill.
- Feature đúng nghĩa theo timeframe.
- Không dùng dữ liệu tương lai.
- Có test cho các contract quan trọng.
- Signal và backtest chỉ dùng dữ liệu đã được xác nhận.
- Alert tương lai ít, rõ ràng và giải thích được.

---

## Related Documents

- [Current State](CURRENT_STATE.md)
- [Architecture Decisions](ARCHITECTURE_DECISIONS.md)
- [Data Pipeline](DATA_PIPELINE.md)
- [AGENTS.md](../AGENTS.md)
- [Database Schema](../docs_db_schema.md)
- [README](../README.md)
---

## CLI reference

See [`docs/CLI_USAGE.md`](CLI_USAGE.md) for the complete production CLI reference, exit codes, parameters, tables read/written, examples, and public Python entry functions.

## Current Phase 0 production ingest behavior

Daily and intraday ingest are separate production pipelines:

```text
python main.py daily [DD/MM/YYYY]
    DailyStockPrice → raw_daily, validation, stock_daily
    DailyStockPrice foreign fields → canonical stock_daily fields
    (DailyIndex/index_daily legacy retained; not called or written)

python main.py intraday-ingest [DD/MM/YYYY] [--symbols SSI HPG]
    IntradayOhlc resolution=1 → raw_intraday, validation, stock_intraday timeframe='1m'
```

`python main.py eod [DD/MM/YYYY]` orchestrates daily ingest, then intraday ingest, then ingest completeness checks. It does not calculate features, signals, or backtests.

`python main.py intraday` remains a legacy feature alias. It reads existing `stock_intraday` data and does not call SSI candle ingest.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.
