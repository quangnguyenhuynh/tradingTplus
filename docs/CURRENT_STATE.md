# Current State

## Document Status

Tài liệu này mô tả trạng thái hiện tại của repository Trading T+ dựa trên code đang có.

Last reviewed against repository code:

```text
14/07/2026
```

Cần phân biệt rõ:

- **Code hiện có trong repository**: đã được đọc và đối chiếu.
- **Schema Supabase thực tế**: chưa thể khẳng định migration nào đã được áp dụng nếu chưa chạy schema check.
- **Dữ liệu production thực tế**: chưa thể khẳng định completeness nếu chưa chạy kiểm tra trên Supabase.
- **SSI account thực tế**: chưa thể khẳng định mọi endpoint hoặc streaming channel đều được tài khoản hỗ trợ.
- **Test runtime hiện tại**: phải chạy lại trong môi trường development trước khi kết luận toàn bộ test pass.

---

## Current Development Phase

Project đang ở:

```text
Phase 0 — Data Foundation and Validation
```

Mục tiêu hiện tại là:

1. Hiểu đúng SSI API và ý nghĩa từng field.
2. Lưu raw data chính xác.
3. Tạo clean data chính xác.
4. Kiểm tra completeness và consistency.
5. Bảo đảm feature có thể rerun và backfill.
6. Chỉ sau đó mới hoàn thiện signal và backtest.

Không ưu tiên:

- tối ưu lợi nhuận;
- tối ưu win rate;
- AI prediction;
- gợi ý phần trăm NAV;
- production alert;
- tự động đặt lệnh.

---

## Overall Status

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| Production CLI | Implemented | Có `sync-master-data`, `init`, `daily`, `intraday-ingest`, `eod`, `features`, `intraday` |
| SSI REST client | Implemented | Login, pagination, retry `401` một lần |
| Master data | Implemented | Symbols, securities, indexes, index components |
| Daily raw ingest | Implemented | `raw_daily` từ `DailyStockPrice` |
| Daily clean ingest | Implemented | `stock_daily` có validation |
| Intraday raw ingest | Partial | Có `raw_intraday`, nhưng chưa giữ full raw JSON payload |
| Intraday clean ingest | Implemented | Chỉ lưu timeframe `1m` |
| Intraday value | Implemented | `round(close * volume)`, là giá trị ước tính |
| Foreign trading | Implemented | Derive từ `DailyStockPrice` |
| Daily index | Implemented | Ghi vào `index_daily` |
| Daily validation | Implemented | Required fields, OHLC, price limit, volume/value |
| Intraday validation | Implemented | Record và batch validation |
| Completeness check | Implemented một phần | Tập trung vào `stock_daily` và `stock_intraday` |
| Feature `1d` | Implemented | Nguồn từ `stock_daily` |
| Feature intraday | Implemented | `1m`, `5m`, `15m`, `60m` |
| Incremental feature | Implemented | Có warm-up và target-date filtering |
| Full feature | Implemented có rủi ro | Có thể dùng nhiều RAM |
| Signal engine | Có code MVP nhưng chưa phù hợp | Đang dùng schema/field cũ |
| Backtest engine | Có code MVP nhưng chưa phải T+ | Dùng `holding_bars`, chưa dùng trading sessions T+3/T+5 |
| Alert scheduler | Not started | Chưa có production scheduler |
| Probability/confidence | Not started | Chưa có model hoặc calibration |
| NAV suggestion | Not started | Chưa có risk sizing engine |
| Mobile application | Not started trong repo này | Chưa phải ưu tiên Phase 0 |
| Production monitoring | Chưa hoàn chỉnh | Chưa có đầy đủ metrics và data-quality history |

---

## Current Production Commands

## 1. Master-data sync

```bash
python main.py sync-master-data
```

Alias:

```bash
python main.py init
```

Hiện thực hiện:

- lấy danh sách mã từ SSI;
- ghi `symbols`;
- lấy `SecuritiesDetails`;
- ghi `securities`;
- lấy danh sách index;
- ghi `indexes`;
- lấy thành phần index;
- ghi `index_components`.

Không thực hiện:

- daily ingest;
- feature;
- signal;
- backtest.

---

## 2. Daily ingest

```bash
python main.py daily DD/MM/YYYY
```

Hiện thực hiện:

```text
SSI DailyStockPrice
    ├── raw_daily
    ├── validate
    └── stock_daily

SSI IntradayOhlc resolution=1
    ├── raw_intraday
    ├── validate candle
    ├── validate batch
    └── stock_intraday timeframe=1m

DailyStockPrice foreign fields
    └── foreign_trading

DailyIndex
    └── index_daily
```

Không thực hiện:

- feature;
- signal;
- backtest;
- alert;
- recommendation.

Khi không truyền ngày, `daily` hiện chọn latest previous weekday.

---

## 3. EOD flow

```bash
python main.py eod DD/MM/YYYY
```

Flow hiện tại:

```text
daily ingest
    ↓
ingest completeness check
    ↓
OK / PARTIAL / FAILED
```

`eod` không chạy feature.

README hiện đã được cập nhật để mô tả `eod` không chạy feature; hành vi trong code vẫn là source of truth.

---

## 4. Explicit feature flow

```bash
python main.py features \
  --mode incremental \
  --date DD/MM/YYYY \
  --symbols SSI HPG \
  --timeframes 1m 5m 15m 60m 1d
```

Feature được chạy riêng sau ingest và validation.

Supported modes:

```text
incremental
full
```

Supported timeframes:

```text
1m
5m
15m
60m
1d
```

---

## 5. Intraday command

```bash
python main.py intraday --symbols SSI HPG
```

Trạng thái hiện tại:

- là legacy compatibility alias;
- chạy incremental feature;
- không gọi SSI để ingest candle mới;
- mặc định tính `1m`, `5m`, `15m`;
- không cho phép `1d`.

Tên command dễ gây hiểu nhầm vì nó không phải intraday ingest pipeline.

---

## Implementation Status

## 1. SSI REST Client

### Đã có

- Đăng nhập bằng consumer ID và consumer secret.
- Lưu access token trong instance.
- Gửi Bearer token.
- Timeout cho request.
- Nếu gặp `401`:
  1. login lại;
  2. retry request một lần.
- Pagination với:
  - `pageIndex`;
  - `pageSize`;
  - `totalRecord` khi có.
- Có khoảng nghỉ ngắn giữa các page.
- Có xử lý một số dạng response:
  - `dataList`;
  - `data`;
  - `items`.

### Endpoint đang được code sử dụng

- `Securities`;
- `SecuritiesDetails`;
- `IndexList`;
- `IndexComponents`;
- `DailyStockPrice`;
- `IntradayOhlc`;
- `DailyIndex`.

### Không được hardcode như public endpoint

- standalone `ForeignTrading`;
- REST market depth/order book.

Foreign trading hiện derive từ `DailyStockPrice`.

Order book chỉ có thể lấy từ:

- SSI streaming quote;
- hoặc account-specific endpoint được cấu hình rõ ràng.

### Chưa được xác nhận đầy đủ

- API rate limit thực tế.
- Pagination behavior trên mọi endpoint.
- Field units trên toàn bộ market.
- Account permission cho streaming channel.
- Behavior trong ngày nghỉ hoặc ngày đặc biệt.
- Timestamp là bar start hay bar end.

---

## 2. Master Data

### Đã có

Các bảng chính:

```text
symbols
securities
indexes
index_components
```

Master pipeline có thể:

- lấy mã theo market;
- map metadata chứng khoán;
- map index;
- map index components;
- upsert lại dữ liệu.

### Điểm cần kiểm tra thêm

- Symbol universe có bao gồm toàn bộ loại chứng khoán cần phân tích hay không.
- Có cần loại DER, warrant, ETF hoặc bond khỏi universe T+ hay không.
- Security đang ngừng giao dịch có được loại khỏi active universe hay không.
- Index component có ngày hiệu lực hay chỉ lưu trạng thái mới nhất.
- Master data có cần lưu lịch sử thay đổi hay không.

---

## 3. Raw Daily Data

### Đã có

`raw_daily` hiện lưu:

- `symbol`;
- `trading_date`;
- `data_hash`;
- full source `payload`.

Nguồn:

```text
DailyStockPrice
```

Conflict key dự kiến:

```text
symbol,trading_date,data_hash
```

### Điểm tốt

- Có payload gốc để đối chiếu.
- Có hash phục vụ idempotency.
- Raw được ghi trước clean validation.
- Daily clean record có thể được tái tạo từ source payload.

### Cần kiểm tra thêm

- Unique index đã được áp dụng trong Supabase thực tế chưa.
- Data hash có ổn định khi JSON key order thay đổi hay không.
- Có cần thêm:
  - source endpoint;
  - ingest time;
  - API request parameters;
  - API response metadata;
  - mapper version.

---

## 4. Clean Daily Data

### Đã có

`stock_daily` là nguồn daily chính.

Nguồn:

```text
SSI DailyStockPrice
```

Các nhóm field hiện được map:

- price change;
- percent change;
- ceiling;
- floor;
- reference;
- open;
- high;
- low;
- close;
- average price;
- adjusted close;
- match volume/value;
- deal volume/value;
- total traded volume/value;
- foreign buy/sell volume/value;
- net foreign volume/value;
- foreign room;
- buy/sell trade counts;
- raw source.

Conflict key:

```text
symbol,trading_date
```

### Quy tắc hiện tại

Clean row chỉ được ghi nếu:

- source đúng requested symbol;
- source đúng requested trading date;
- daily validation không có error.

### Vai trò

`stock_daily` là source of truth cho:

```text
feature timeframe = 1d
```

Không tính canonical feature `1d` từ intraday.

---

## 5. Raw Intraday Data

### Đã có

`raw_intraday` hiện lưu:

- symbol;
- UTC time;
- open;
- high;
- low;
- close;
- volume;
- data hash.

Nguồn:

```text
IntradayOhlc resolution=1
```

Conflict key:

```text
symbol,time,data_hash
```

### Khoảng thiếu

`raw_intraday` hiện chưa giữ full raw candle JSON payload.

Hash được tính từ source candle JSON, nhưng source JSON không được lưu đầy đủ.

Hệ quả:

- khó kiểm tra field mới sau ingest;
- khó chứng minh mapper không bỏ mất field;
- khó debug khi SSI thay đổi response;
- khó backfill lại clean mapping mà không gọi SSI lần nữa.

Đây là khoảng thiếu quan trọng của raw layer.

Mọi thay đổi bổ sung raw payload phải:

- kiểm tra schema hiện tại;
- tạo migration;
- xác định data cũ có cần backfill hay không;
- không thực hiện kèm task không liên quan.

---

## 6. Clean Intraday Data

### Đã có

`stock_intraday` là clean intraday table.

Timeframe duy nhất được phép lưu:

```text
1m
```

Database client từ chối:

- timeframe khác `1m`;
- feature columns bị ghi nhầm vào `stock_intraday`.

Conflict key:

```text
symbol,timeframe,time
```

### Timestamp

SSI candle time được hiểu theo:

```text
Asia/Ho_Chi_Minh
```

Sau đó chuyển sang UTC để lưu.

Timestamp không parse được sẽ bị bỏ qua.

### Partition

`stock_intraday` được partition theo tháng.

Database client gọi RPC:

```text
create_partition_if_not_exists
```

trước khi upsert dữ liệu từng tháng.

### Intraday value

Công thức hiện tại:

```text
value = round(close * volume)
```

Ý nghĩa:

- giá trị giao dịch ước tính theo close của candle;
- không phải exact turnover từ SSI;
- chỉ phục vụ research khi đã ghi rõ provenance.

Nếu close hoặc volume thiếu:

```text
value = NULL
```

Không tự thay bằng `0`.

---

## 7. Foreign Trading

### Đã có

`foreign_trading` hiện được derive từ các foreign fields trong `DailyStockPrice`.

Các nhóm dữ liệu:

- foreign buy volume;
- foreign sell volume;
- foreign buy value;
- foreign sell value;
- net foreign volume;
- net foreign value;
- foreign room;
- raw source row.

Conflict key daily:

```text
symbol,trading_date
```

### Known inefficiency

Daily pipeline hiện có thể gọi `DailyStockPrice` hai lần cho cùng symbol/date:

1. lấy daily raw/clean;
2. lấy foreign trading.

Đây là duplicate API request.

Chưa cần sửa kèm task khác. Khi sửa phải:

- reuse daily payload đã có;
- giữ nguyên mapper contract;
- thêm test để tránh thay đổi output.

---

## 8. Index Data

### Đã có

Các bảng:

```text
indexes
index_components
index_daily
```

Index quan trọng đang được cấu hình gồm:

- VNINDEX;
- VN30;
- HNXIndex;
- HNX30;
- HNXUpcomIndex;
- UPCOMIndex.

`index_daily` lưu:

- index value;
- change;
- ratio change;
- total trade;
- volume/value;
- advances;
- no changes;
- declines;
- ceilings;
- floors;
- raw payload.

### Cần kiểm tra thêm

- Tên index code SSI thực tế có nhất quán hay không.
- Có index code nào trả rỗng theo từng exchange hay không.
- Có cần filter nhóm index phù hợp với product hay không.
- Daily index có được kiểm tra completeness cùng stock data hay không.
- Index component có lịch sử thay đổi hay chưa.

---

## 9. Daily Validation

### Đã có

Daily validator kiểm tra:

- required fields;
- price field hợp lệ;
- price dương khi có giao dịch;
- volume/value không âm;
- quan hệ OHLC;
- high không thấp hơn các thành phần khác;
- low không cao hơn các thành phần khác;
- floor ≤ reference ≤ ceiling;
- OHLC nằm trong floor/ceiling;
- price change so với close − reference;
- percent change;
- total volume so với match + deal;
- total value so với match + deal.

### Error behavior

Nếu có validation error:

- `stock_daily` không được ghi;
- clean intraday của cùng symbol/date cũng không được ghi.

### Warning behavior

Warning được log nhưng không nhất thiết chặn ghi clean daily.

### Cần kiểm chứng thêm

- Price unit của SSI.
- Tolerance theo tick size.
- Adjusted close behavior.
- Daily volume/value fields trên các loại chứng khoán khác nhau.
- Trường hợp symbol không giao dịch nhưng vẫn có daily row.
- Trường hợp giá bằng `0` hợp lệ hay không.

---

## 10. Intraday Validation

### Record validation đã có

Kiểm tra:

- required fields;
- timeframe phải là `1m`;
- UTC timezone-aware timestamp;
- OHLC phải dương;
- volume không âm;
- value không âm;
- quan hệ OHLC;
- price nằm trong floor/ceiling.

### Batch validation đã có

Kiểm tra:

- empty batch;
- duplicate timestamp;
- unsorted input;
- candle ngoài trading session;
- missing 1-minute interval;
- last intraday close so với daily close;
- tổng volume intraday so với daily matched volume.

### Trading session hiện tại

```text
09:00–11:30
13:00–15:00
Asia/Ho_Chi_Minh
```

Lunch break không được xem là missing interval.

### Cần kiểm chứng thêm

- Candle timestamp là bar start hay bar end.
- Candle tại `09:00` có thật sự được SSI trả không.
- ATO và ATC được biểu diễn ra sao.
- Có candle tại `11:30` và `15:00` hay không.
- Session rule của HOSE, HNX và UPCOM có cần tách không.
- Symbol halt hoặc không phát sinh giao dịch được đánh giá thế nào.
- Gap do không có giao dịch có phải missing data hay response đúng của SSI.
- Daily matched volume có luôn bằng tổng intraday volume hay không.

Không được dùng một con số cố định như `226` để kết luận mọi ngày đầy đủ.

---

## 11. Completeness Check

### Đã có

Command:

```bash
python scripts/check_ingest.py --date DD/MM/YYYY
```

Check hiện tại đọc:

- symbol universe;
- `stock_daily`;
- `stock_intraday` timeframe `1m`;
- `index_daily` count;
- `foreign_trading` count.

Theo từng symbol, summary có:

- daily present;
- intraday candle count;
- first candle;
- last candle;
- duplicate count;
- missing interval count;
- missing minutes;
- status.

### Trạng thái

#### `FAILED`

Khi:

- không có `stock_daily`; hoặc
- không có `stock_intraday`.

#### `PARTIAL`

Khi:

- thiếu daily symbol;
- thiếu intraday symbol;
- có duplicate;
- có missing interval.

#### `OK`

Khi không phát hiện các vấn đề trên theo rule hiện tại.

### Khoảng thiếu

Completeness hiện chưa bao phủ đầy đủ:

- `raw_daily`;
- `raw_intraday`;
- `securities`;
- `indexes`;
- `index_components`;
- field-level null rate;
- cross-table raw-to-clean mapping;
- foreign-trading completeness;
- index completeness;
- partition completeness;
- order-book snapshot completeness.

`orderbook_snapshot_count` hiện đang hardcode:

```text
0
```

chứ chưa query dữ liệu thực tế.

---

## 12. Database Layer

### Đã có

- Supabase client singleton.
- Batch upsert.
- JSON sanitization.
- Bounded retry.
- Exponential backoff có jitter.
- Reconnect cho lỗi auth/JWT.
- Logging batch size và time range.
- Critical conflict tables.
- Fail-fast khi critical table thiếu matching unique constraint.
- Fail-fast khi schema thiếu column.
- Monthly partition handling cho `stock_intraday`.

### Critical conflict keys

Các bảng critical gồm:

- `stock_intraday`;
- `features`;
- `backtest_data`;
- `foreign_trading`;
- `orderbook_snapshot`;
- streaming snapshot tables;
- `trading_signals`;
- `securities`;
- `stock_daily`;
- `raw_daily`;
- `indexes`;
- `index_components`;
- `index_daily`.

### Cần xác nhận trong Supabase

- Tất cả unique indexes đã tồn tại.
- Tất cả migrations đã được áp dụng đúng thứ tự.
- Function `create_partition_if_not_exists` tồn tại.
- Service role có quyền gọi RPC.
- Partition mới được tạo đúng.
- Không có schema drift giữa local `schema.sql` và production.
- Không còn dữ liệu duplicate từ các version cũ.

---

## 13. Feature Pipeline

### Đã có

Một bảng feature chung:

```text
features
```

Conflict key:

```text
symbol,timeframe,time
```

Supported timeframes:

```text
1m
5m
15m
60m
1d
```

### Nguồn dữ liệu

| Timeframe | Source |
|---|---|
| `1d` | `stock_daily` |
| `1m` | `stock_intraday` 1m |
| `5m` | aggregate từ 1m |
| `15m` | aggregate từ 1m |
| `60m` | aggregate từ 1m |

Không ghi candle aggregate ngược vào `stock_intraday`.

### Feature groups hiện có

- OHLC;
- volume;
- value;
- returns;
- EMA9;
- EMA20;
- EMA50;
- EMA relationship flags;
- RSI14;
- MACD;
- MACD signal;
- MACD histogram;
- volume MA20;
- volume ratio;
- value MA20;
- value ratio;
- rolling high;
- rolling low;
- breakout flags;
- intraday VWAP;
- close versus VWAP;
- distance to VWAP;
- candle range;
- candle body;
- candle body percentage;
- close position in candle.

### Incremental mode

Hiện lấy:

- target-date intraday data;
- tối đa 300 intraday warm-up rows;
- tối đa 150 daily rows.

Sau khi tính trên warm-up + target data, chỉ upsert output trong target date.

### Full mode

Hiện:

1. fetch `stock_intraday` theo page;
2. gom toàn bộ rows của symbol vào list;
3. tạo DataFrame;
4. tính toàn bộ requested timeframes;
5. upsert toàn bộ feature output.

### Rủi ro full mode

Pagination chỉ giới hạn kích thước mỗi DB request.

Toàn bộ history của một symbol vẫn được giữ trong RAM.

Full mode chưa phù hợp để chạy toàn universe và lịch sử lớn nếu chưa đo:

- memory;
- runtime;
- request count;
- upsert duration.

### Chưa được chứng minh đầy đủ

- Incremental output bằng full output trên overlapping rows.
- Warm-up 300 intraday rows đủ cho mọi timeframe.
- Warm-up 150 daily rows đủ cho mọi future feature.
- Aggregation không tạo bar qua lunch break.
- Timestamp của aggregate bar đúng mong muốn.
- Incomplete current candle được xử lý đúng.
- Feature formulas đã được đối chiếu với nguồn thứ hai.
- Null behavior sau warm-up được thống nhất.
- Feature versioning.

---

## 14. Signal Engine

### Code hiện có

Repository có:

```text
src/engine/signal_engine.py
```

và một số strategy module:

- reversal;
- breakout;
- trend.

### Trạng thái thực tế

Signal engine hiện là code cũ/MVP và chưa phù hợp với current feature schema.

Signal query đang yêu cầu các field như:

```text
rsi
ema_20
ema_50
bb_upper
volume_spike
```

Trong khi feature engine hiện sử dụng các field như:

```text
rsi14
ema20
ema50
```

Một số field signal yêu cầu không có trong current feature output:

```text
bb_upper
volume_spike
```

### Check times hiện tại trong code

```text
09:45
10:30
13:45
14:30
```

Không khớp mục tiêu sản phẩm đã chốt:

```text
09:30
11:30
13:30
14:30
```

### Conflict key không thống nhất

Signal engine hiện upsert theo:

```text
symbol,signal_type,bucket_time
```

Trong khi các phần khác của repository mô tả key có thêm timeframe/time.

Cần kiểm tra schema thực tế trước khi sửa.

### Kết luận

Signal engine:

```text
NOT PRODUCTION READY
```

Không được tự động gọi từ:

- daily;
- eod;
- features;
- intraday.

Cần một task riêng để thiết kế lại signal contract sau khi feature được kiểm chứng.

---

## 15. Backtest Engine

### Code hiện có

Repository có MVP backtest:

```text
src/engine/backtest_engine.py
```

Backtest hiện hỗ trợ:

- input in-memory;
- long và short direction;
- initial capital;
- position size percentage;
- holding bars;
- fee percentage;
- minimum signal score;
- bỏ overlapping trade cùng symbol/timeframe;
- PnL;
- return;
- win rate;
- max drawdown;
- simple Sharpe;
- trade list.

### Điểm tốt

- Logic tách thành function có thể unit test.
- Không bắt buộc Supabase để test core logic.
- Có config rõ ràng.
- Có xử lý fee.
- Có basic overlap rule.

### Chưa phù hợp với sản phẩm T+

Backtest hiện thoát lệnh theo:

```text
holding_bars
```

Không phải:

```text
T+1
T+3
T+5 trading sessions
```

Backtest hiện chưa xác định đầy đủ:

- entry tại close hay next open;
- khớp lệnh sau signal bao lâu;
- giá trần/sàn;
- thanh khoản;
- không khớp được lệnh;
- slippage;
- lot size;
- transaction tax;
- settlement restrictions;
- missing future daily row;
- corporate action;
- adjusted price;
- trading calendar;
- portfolio-level capital allocation.

`run_backtest_engine` hiện tải feature và signal trong cùng target date, phù hợp hơn với intraday bar backtest hơn T+3/T+5.

### Kết luận

Backtest engine:

```text
MVP / RESEARCH ONLY
```

Không được dùng để đánh giá khả năng sinh lợi hiện tại của sản phẩm.

---

## 16. Streaming và Order Book

### Code hiện có

Repository đã có các thành phần liên quan đến:

- SSI SignalR negotiation;
- streaming connection;
- quote snapshot;
- trade snapshot;
- foreign snapshot;
- index snapshot;
- order-book mapping;
- manual snapshot scripts;
- streaming test scripts.

### Kiến trúc hiện hiểu

SSI FCData streaming dùng classic ASP.NET SignalR, không phải raw websocket endpoint đơn giản.

Order-book depth có thể xuất hiện trong quote message qua các field như:

```text
BidPrice1
BidVol1
AskPrice1
AskVol1
...
```

### Chưa được xác nhận

- Tài khoản hiện tại có quyền streaming không.
- Channel name chính xác trong production.
- Message frequency.
- Reconnect behavior dài hạn.
- Snapshot capture có bỏ sót message không.
- Thời điểm snapshot chính xác.
- Độ sâu đủ 10 level cho mọi symbol không.
- Có thể chạy ổn định trên GitHub Actions không.
- Order-book history cần lưu bao lâu.
- Snapshot cadence phù hợp với mục tiêu T+ hay không.

### Trạng thái

```text
IMPLEMENTATION EXISTS
LIVE RELIABILITY NOT YET VERIFIED
```

Order book chưa được xem là dependency bắt buộc của Phase 0 daily pipeline.

---

## 17. Smoke, Debug và Maintenance Scripts

### Đã có

Các nhóm script hiện có:

- SSI API check;
- Supabase check;
- symbol check;
- complete ingest smoke test;
- schema check;
- API inspector;
- ingest completeness;
- feature runner;
- sample backfill;
- intraday value backfill;
- streaming tests;
- order-book snapshot;
- SignalR debug;
- cleanup SQL.

### Safety behavior đã có

`check_complete_ssi_ingest.py`:

- read-only mặc định;
- `--write` yêu cầu explicit date;
- weekend/future guard;
- intraday write cần `--write-intraday`;
- có `--force` cho trường hợp thật sự cần.

`backfill_sample.py`:

- bắt buộc from date;
- bắt buộc to date;
- bắt buộc symbols;
- không còn hardcoded sample date;
- chặn future date mặc định.

### Cần cải thiện thêm

- Chuẩn hóa output JSON summary.
- Chuẩn hóa exit code.
- Ghi rõ script nào read-only.
- Ghi rõ script nào write.
- Ghi rõ table bị ảnh hưởng.
- Thêm dry-run cho các maintenance script còn thiếu.
- Thêm confirmation scope cho delete/update script.

---

## 18. Tests

### Test structure đã có

Repository có test cho các nhóm như:

- CLI;
- EOD pipeline;
- EOD dry run;
- fetch one day;
- feature engine;
- intraday value;
- backtest engine;
- daily validator;
- intraday validator;
- SSI/streaming parser ở một số script.

### Chưa được khẳng định trong tài liệu này

- Toàn bộ test suite hiện đang pass.
- Test có chạy với Python version nào.
- Test integration có credential hay không.
- GitHub Actions hiện pass hay fail.
- Code coverage bao nhiêu.
- Production schema có khớp test fixtures không.

### Test cần bổ sung hoặc củng cố

- Raw-to-clean mapping snapshot test.
- Exact SSI sample payload test.
- Daily symbol/date mismatch test.
- Non-trading-day behavior.
- Holiday behavior.
- Full versus incremental feature equivalence.
- Session-aware 5m/15m/60m aggregation.
- Lunch-break boundary.
- Incomplete latest candle.
- Partition creation.
- Unique-index failure.
- Large pagination.
- Foreign payload reuse.
- T+ session-based outcome labeling.
- Signal schema compatibility sau khi signal được redesign.

---

## Completed Work

Các phần sau đã có implementation trong code.

### Core infrastructure

- Python application structure.
- Main CLI.
- SSI REST client.
- Supabase client.
- Config qua environment.
- Database retry có giới hạn.
- Batch upsert.
- Basic logging.
- Schema và migration files.

### Master data

- Symbols sync.
- Securities details sync.
- Index list sync.
- Index component sync.

### Daily ingest

- `DailyStockPrice` fetch.
- `raw_daily`.
- `stock_daily`.
- Daily validation.
- Symbol/date match guard.
- Daily index ingest.
- Foreign fields mapping.

### Intraday ingest

- `IntradayOhlc` resolution 1.
- Vietnam time → UTC conversion.
- Invalid timestamp rejection.
- `raw_intraday`.
- `stock_intraday` 1m.
- Individual validation.
- Batch validation.
- Duplicate handling.
- Estimated intraday value.
- Monthly partition handling.

### Data quality

- Daily OHLC checks.
- Intraday OHLC checks.
- Price-limit checks.
- Duplicate checks.
- Gap checks.
- Daily/intraday close comparison.
- Daily/intraday volume comparison.
- Per-symbol completeness summary.

### Features

- Explicit feature CLI.
- One `features` table.
- Daily source separation.
- Intraday aggregation.
- Incremental mode.
- Full mode.
- Warm-up loading.
- Multi-timeframe output.
- Idempotent feature upsert.

### Safety

- Read-only smoke mode.
- Explicit write flags.
- Date guards.
- Scoped sample backfill.
- Bounded API/DB retry.
- Critical conflict-key fail-fast.

---

## In Progress

Các phần sau đã có nền tảng nhưng chưa được xác nhận đủ để xem là hoàn thành.

### SSI contract verification

- Field meaning.
- Units.
- Timestamp semantics.
- Trading-session semantics.
- Empty response behavior.
- Special trading days.
- Market-specific differences.

### Raw data quality

- Full raw intraday payload.
- Raw ingest metadata.
- Raw/clean traceability report.
- Historical raw-data completeness.

### Completeness

- Dynamic expected-session model.
- Exchange calendar.
- Auction handling.
- Halt handling.
- Index completeness.
- Foreign completeness.
- Raw-table completeness.
- Order-book completeness.

### Feature reproducibility

- Full/incremental comparison.
- Warm-up sufficiency.
- Session-safe aggregation.
- Incomplete-bar handling.
- Formula validation.
- Feature versioning.

### Documentation

- `PROJECT_OVERVIEW.md`.
- `DATA_PIPELINE.md`.
- `CURRENT_STATE.md`.
- `ARCHITECTURE_DECISIONS.md`.
- README cleanup.

README đã được cập nhật để không mô tả `eod` có chạy feature.

### Operational readiness

- Production schedule.
- Data-quality history.
- Alert on failed ingest.
- Runtime monitoring.
- Rate-limit monitoring.
- Partition monitoring.
- Backfill runbook.

---

## Not Started or Not Production Ready

Các hạng mục sau chưa nên được xem là hoàn thành.

### Signal

- Current signal engine chưa tương thích feature schema.
- Check times chưa đúng mục tiêu.
- Chưa có multi-timeframe T+ signal contract.
- Chưa có signal versioning.
- Chưa có confidence calibration.
- Chưa có duplicate/no-spam policy hoàn chỉnh.

### T+ backtest

- Chưa có T+1/T+3/T+5 session outcomes.
- Chưa có next-session execution model.
- Chưa có portfolio-level simulation.
- Chưa có slippage model phù hợp Việt Nam.
- Chưa có price-limit execution rule.
- Chưa có corporate-action handling.
- Chưa có data-snooping controls.

### Alert system

- Chưa có scheduler cho:
  - `09:30`;
  - `11:30`;
  - `13:30`;
  - `14:30`.
- Chưa có alert deduplication.
- Chưa có alert suppression.
- Chưa có explanation template.
- Chưa có delivery channel.
- Chưa có watchlist-based filtering.

### Risk và NAV suggestion

- Chưa có position sizing.
- Chưa có portfolio exposure limit.
- Chưa có confidence-to-NAV mapping.
- Chưa có drawdown-based risk adjustment.
- Chưa có liquidity-based sizing.

### AI

- Chưa có training dataset đã được xác nhận.
- Chưa có outcome labels đáng tin.
- Chưa có feature leakage audit.
- Chưa có model validation.
- Chưa có probability calibration.
- Chưa có drift monitoring.

---

## Known Issues

## 1. README không đồng nhất với code

Một số đoạn README vẫn nói:

```text
eod = daily ingest + intraday ingest + completeness
```

Trong code hiện tại:

```text
eod = daily ingest + intraday ingest + completeness
```

Feature phải chạy riêng bằng:

```bash
python main.py features ...
```

README đã được cập nhật để giữ một bảng `features` có cột `timeframe`; không tách `daily_features`/`intraday_features`.

---

## 2. Signal engine dùng feature schema cũ

Signal engine đang query:

```text
rsi
ema_20
ema_50
bb_upper
volume_spike
```

Feature schema hiện dùng:

```text
rsi14
ema20
ema50
```

Signal engine có thể lỗi query hoặc không chạy đúng.

---

## 3. Signal check times không đúng mục tiêu

Code hiện dùng:

```text
09:45
10:30
13:45
14:30
```

Mục tiêu sản phẩm:

```text
09:30
11:30
13:30
14:30
```

Không sửa chỉ bằng cách đổi constant. Cần thiết kế lại snapshot data contract trước.

---

## 4. Signal conflict key chưa thống nhất

Signal engine, database client, schema và docs có thể đang mô tả conflict key khác nhau.

Phải kiểm tra schema Supabase và migration trước khi sửa.

---

## 5. Backtest chưa phải T+ backtest

Current MVP dùng future bars thay vì future trading sessions.

Không được dùng kết quả hiện tại để đánh giá chiến lược T+3/T+5.

---

## 6. Raw intraday chưa giữ full source payload

Raw intraday hiện không có full JSON source row.

Điều này làm giảm khả năng audit và remap dữ liệu lịch sử.

---

## 7. Foreign trading gọi lại DailyStockPrice

Daily source có thể bị gọi lặp cho cùng symbol/date.

Ảnh hưởng:

- tăng request count;
- tăng runtime;
- tăng nguy cơ rate limit;
- hai lần gọi có thể nhận response khác nhau nếu API thay đổi trong lúc chạy.

---

## 8. Daily và EOD có default-date behavior khác nhau

`daily` mặc định dùng latest previous weekday.

`eod` mặc định dùng latest weekday on or before today.

Nếu chạy `eod` trong ngày giao dịch trước khi phiên kết thúc, có thể ingest dữ liệu chưa hoàn chỉnh.

Production schedule nên luôn truyền explicit trading date.

---

## 9. Full feature mode có nguy cơ RAM cao

Toàn bộ intraday history của từng symbol được gom vào memory.

Rủi ro tăng theo:

- số ngày;
- số candle;
- số timeframe;
- số symbol chạy đồng thời.

---

## 10. Completeness status chưa dùng index và foreign làm điều kiện chính

`index_daily_count` và `foreign_trading_count` được hiển thị nhưng chưa ảnh hưởng đầy đủ đến overall status.

Có thể xuất hiện trạng thái `OK` dù index hoặc foreign data thiếu.

---

## 11. Order-book completeness đang hardcode 0

`orderbook_snapshot_count` chưa query database thực tế.

Không dùng field này để kết luận order-book data hiện thiếu hay đủ.

---

## 12. Daily ingest status có thể chưa phản ánh API empty toàn universe

Daily status hiện chủ yếu dựa trên exception count.

Nếu API trả rỗng mà không raise exception, daily summary có thể chưa phản ánh lỗi đầy đủ.

EOD completeness hiện giúp phát hiện `stock_daily_count = 0` hoặc `stock_intraday_count = 0`, nhưng daily command chạy riêng vẫn cần được kiểm tra kỹ.

---

## 13. Trading calendar chưa hoàn chỉnh

Code hiện có weekday-based defaults và weekend guards.

Chưa có exchange holiday calendar hoàn chỉnh.

Ngày trong tuần không đồng nghĩa chắc chắn là trading day.

---

## 14. Session configuration chưa được xác nhận hoàn toàn

Validator đang dùng:

```text
09:00–11:30
13:00–15:00
```

Cần kiểm chứng với response SSI thực tế, ATO/ATC và ý nghĩa timestamp.

---

## 15. Feature full/incremental equivalence chưa được chứng minh

Cùng một source history cần tạo cùng kết quả trên overlapping rows.

Hiện có thiết kế warm-up nhưng chưa có đủ evidence để kết luận hoàn toàn tương đương.

---

## Current Risks

## Data correctness risk

Nếu hiểu sai:

- volume;
- value;
- timestamp;
- adjusted close;
- foreign fields;
- total match versus total traded;

thì feature và backtest sẽ sai dù code chạy không lỗi.

Mức độ:

```text
HIGH
```

---

## Schema drift risk

Code phụ thuộc vào:

- columns;
- unique indexes;
- RPC;
- partitions;
- conflict keys.

Nếu production Supabase không khớp migration, pipeline có thể fail hoặc ghi không đúng.

Mức độ:

```text
HIGH
```

---

## Incomplete raw lineage risk

Raw intraday chưa giữ full payload.

Nếu SSI thay đổi mapper contract, dữ liệu cũ khó remap.

Mức độ:

```text
MEDIUM TO HIGH
```

---

## False completeness risk

Gap-based validation có thể hiểu nhầm:

- symbol không phát sinh giao dịch;
- trading halt;
- auction;
- SSI không trả candle zero-volume;

thành missing data.

Ngược lại, đủ số candle cũng không chứng minh field values đúng.

Mức độ:

```text
HIGH
```

---

## Full feature memory risk

Full mode có thể dùng quá nhiều RAM khi backfill toàn lịch sử.

Mức độ:

```text
MEDIUM
```

---

## Documentation drift risk

README và code hiện có một số mâu thuẫn.

Agent hoặc developer có thể sửa theo docs cũ và làm hỏng kiến trúc đã chốt.

Mức độ:

```text
MEDIUM TO HIGH
```

---

## Premature strategy risk

Repository có signal/backtest MVP nên dễ tạo cảm giác project đã sẵn sàng đánh giá lợi nhuận.

Thực tế source data và feature vẫn đang trong quá trình kiểm chứng.

Mức độ:

```text
HIGH
```

---

## External dependency risk

Pipeline phụ thuộc vào:

- SSI API availability;
- SSI credentials;
- account permission;
- Supabase availability;
- network;
- schema deployment.

Mức độ:

```text
MEDIUM
```

---

## Open Questions

## SSI và source data

1. `IntradayOhlc.Time` là thời điểm bắt đầu hay kết thúc candle?
2. `IntradayOhlc.Volume` đã được xác nhận là volume riêng của candle trên mọi market chưa?
3. Daily price và intraday price dùng cùng unit chưa?
4. Total value của SSI dùng đơn vị nào?
5. `TotalMatchVol` có luôn bằng tổng volume intraday không?
6. ATO và ATC được biểu diễn trong intraday data ra sao?
7. API trả gì trong ngày symbol không có giao dịch?
8. API trả gì trong trading halt?
9. API có giới hạn date range hoặc page size thực tế không?
10. Có endpoint hoặc field thay đổi theo SSI account version không?

## Trading calendar và completeness

1. Nguồn trading calendar chính thức sẽ lấy ở đâu?
2. Completeness nên dựa trên expected timestamp set nào?
3. Có cần rule riêng cho HOSE, HNX và UPCOM không?
4. Candle zero-volume có được SSI trả không?
5. Missing candle do không giao dịch có được xem là lỗi không?
6. Phiên rút ngắn được cấu hình thế nào?
7. Khi nào một ngày được đánh dấu `COMPLETE`, `PARTIAL`, `NO_DATA`, `NON_TRADING_DAY`?

## Raw và clean data

1. Có bổ sung full payload cho `raw_intraday` không?
2. Có cần mapper version trong raw/clean row không?
3. Có cần ingest run ID không?
4. Có cần source endpoint và request params trong raw table không?
5. Data cũ có đủ để backfill raw payload không?

## Features

1. Warm-up cần bao nhiêu bar cho từng timeframe?
2. Aggregate timestamp dùng bar start hay bar end?
3. `60m` phải chia theo session thế nào?
4. Incomplete current candle có được tính không?
5. Feature nào thật sự cần cho T+3/T+5?
6. Feature nào chỉ dùng cho timing?
7. Có cần feature version không?
8. Feature incremental và full sẽ được so sánh bằng tolerance nào?

## Signals

1. Signal nên tạo từ daily setup trước hay scan tất cả timeframe cùng lúc?
2. `1d`, `60m`, `15m` kết hợp theo rule nào?
3. `5m` và `1m` có vai trò gì trong final signal?
4. Một symbol có thể có bao nhiêu signal trong ngày?
5. Khi nào suppress signal lặp?
6. Signal score khác probability như thế nào?
7. Reason format sẽ lưu text hay structured JSON?
8. Signal version được lưu ở đâu?

## Backtest

1. Entry price dùng next open, snapshot close hay giá khác?
2. T+3/T+5 được tính theo trading session nào?
3. Nếu thiếu giá exit thì xử lý thế nào?
4. Có cho overlapping signals không?
5. Position engine có cần trong MVP không?
6. Fee, tax và slippage dùng bao nhiêu?
7. Price-limit và không khớp lệnh được mô phỏng thế nào?
8. Corporate action được xử lý bằng adjusted price hay raw price?

## Alerts

1. Alert chạy đúng các mốc:
   - `09:30`;
   - `11:30`;
   - `13:30`;
   - `14:30`;
   hay cần thay đổi?
2. Snapshot lấy candle đóng gần nhất nào?
3. Alert gửi cho toàn universe hay watchlist?
4. Điều kiện suppress alert là gì?
5. Alert có cần probability tối thiểu không?
6. Alert channel sẽ là mobile push, Telegram, email hay Supabase realtime?

---

## Next Steps

Thứ tự dưới đây bám theo Phase 0. Không chuyển sang bước sau khi bước trước chưa có evidence.

## Step 1 — Đồng bộ documentation với code

Cần hoàn thiện:

- `PROJECT_OVERVIEW.md`;
- `DATA_PIPELINE.md`;
- `CURRENT_STATE.md`;
- `ARCHITECTURE_DECISIONS.md`;
- cleanup README.

Mục tiêu:

- không còn mô tả `eod` tự chạy feature;
- không còn đề xuất tự tách bảng `features`;
- command và architecture nhất quán.

---

## Step 2 — Xác minh schema Supabase

Chạy read-only schema check.

Kiểm tra:

- tables;
- columns;
- data types;
- unique indexes;
- partition function;
- migrations applied;
- conflict keys.

Không ingest hoặc backfill lớn trước khi schema check pass.

---

## Step 3 — Chọn một sample chuẩn

Chọn:

- 1 symbol thanh khoản cao;
- 1 trading date bình thường;
- 1 ngày không giao dịch hoặc ngày nghỉ;
- 1 symbol ít thanh khoản nếu cần.

Ví dụ sample phải được ghi rõ, không hardcode vào production code.

---

## Step 4 — Inspect SSI read-only

Chạy inspector để lưu evidence:

- raw `DailyStockPrice`;
- raw `IntradayOhlc`;
- mapped daily;
- mapped intraday;
- foreign fields;
- daily index;
- symbol/date matching;
- units;
- timestamp samples.

Không ghi database trong bước này.

---

## Step 5 — Validate raw và clean mapping

Với một symbol/date:

1. So sánh raw daily với clean daily.
2. So sánh raw intraday với clean intraday.
3. Kiểm tra timestamp UTC và giờ Việt Nam.
4. Kiểm tra intraday value.
5. Kiểm tra close và volume consistency.
6. Ghi lại field nào chưa hiểu rõ.

---

## Step 6 — Xác minh completeness rules

Kiểm thử trên:

- ngày bình thường;
- ngày nghỉ;
- weekend;
- symbol ít thanh khoản;
- symbol có gap;
- duplicate sample;
- candle ngoài session.

Không chốt universal expected count nếu chưa có căn cứ.

---

## Step 7 — Quyết định raw intraday lineage

Đánh giá việc thêm full payload vào `raw_intraday`.

Nếu làm:

- phải có migration;
- giữ backward compatibility;
- xác định data cũ có backfill được không;
- thêm mapper test;
- không đổi clean schema ngoài phạm vi.

---

## Step 8 — Kiểm tra feature reproducibility

Với một symbol/date:

1. Chạy full.
2. Lưu output sample.
3. Xóa hoặc rerun target rows an toàn.
4. Chạy incremental.
5. So sánh overlapping rows.
6. Kiểm tra từng timeframe.
7. Kiểm tra lunch boundary.
8. Kiểm tra null warm-up.

Chỉ coi feature pipeline ổn định khi kết quả có thể tái tạo.

---

## Step 9 — Xây production data runbook

Runbook cần mô tả:

- schedule;
- explicit trading date;
- master-data frequency;
- daily/EOD flow;
- completeness threshold;
- retry behavior;
- failure handling;
- safe rerun;
- backfill;
- cleanup;
- monitoring.

---

## Step 10 — Chỉ sau Phase 0 mới redesign signal

Signal task tương lai cần:

- đọc current feature schema;
- bỏ field cũ;
- chốt timeframe roles;
- chốt alert times;
- chốt signal storage contract;
- có strategy version;
- có reason rõ ràng;
- không spam;
- không chạy tự động sau feature nếu chưa yêu cầu.

---

## Phase 0 Exit Criteria

Phase 0 chỉ hoàn thành khi có evidence cho các điều kiện sau.

### SSI contract

- Endpoint đã xác nhận.
- Field đã xác nhận.
- Units đã xác nhận.
- Timestamp semantics đã xác nhận.
- Volume semantics đã xác nhận.
- Non-trading-day behavior đã xác nhận.

### Raw data

- Raw daily có lineage đầy đủ.
- Raw intraday lineage được chấp nhận hoặc đã bổ sung.
- Không tạo fake data.
- Có stable conflict key.
- Rerun không tạo duplicate.

### Clean data

- Daily mapper được kiểm chứng.
- Intraday mapper được kiểm chứng.
- Missing giữ đúng `NULL`.
- OHLC validation đáng tin.
- Timezone đúng.
- Daily/intraday consistency được báo cáo.

### Completeness

- Check theo symbol/date.
- Không hardcode universal candle count.
- Có phân biệt missing data và non-trading day.
- Có rule cho session và lunch break.
- Có report đủ để debug.

### Features

- `1d` lấy từ `stock_daily`.
- Intraday lấy từ `stock_intraday` 1m.
- Aggregate không qua session boundary.
- Incremental và full tương đương.
- Không look-ahead.
- Có rerun và backfill.
- Có tests cho formula quan trọng.

### Operations

- Schema verified.
- Migrations documented.
- Smoke test read-only.
- Backfill có scope.
- Debug mặc định read-only.
- Failure được báo rõ.
- Không lộ secret.

Cho đến khi các điều kiện này đạt, project vẫn ở Phase 0.

---

## Related Documents

- [Project Overview](PROJECT_OVERVIEW.md)
- [Architecture Decisions](ARCHITECTURE_DECISIONS.md)
- [Data Pipeline](DATA_PIPELINE.md)
- [AGENTS.md](../AGENTS.md)
- [Database Schema](../docs_db_schema.md)
- [README](../README.md)
---

## Current ingest/CLI state after Issue #69

- `daily` is daily-only production ingest and writes `raw_daily`, `stock_daily`, `foreign_trading`, and `index_daily`.
- `intraday-ingest` is the production SSI `IntradayOhlc` 1m ingest and writes `raw_intraday` and `stock_intraday` only.
- `eod` calls daily ingest, intraday ingest, then completeness checks and returns `daily_summary`, `intraday_summary`, `ingest_summary`, and final status.
- `features` is the explicit feature pipeline.
- `intraday` is still a legacy feature alias for existing `stock_intraday` data; it does not ingest candles.
- No migration or automatic backfill is required by the split.

See [`CLI_USAGE.md`](CLI_USAGE.md) for command syntax and public entry functions.
