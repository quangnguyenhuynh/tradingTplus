# Current State

## Document status

Tài liệu này mô tả trạng thái hiện tại của repository Trading T+ dựa trên code, migration, test và workflow đang có.

Last reviewed against repository code:

```text
18/07/2026
```

Repository commit dùng để đối chiếu:

```text
59e36b1310c4e435f1c426bd2d19276262f47922
```

Phạm vi đã đọc và đối chiếu gồm:

- `main.py`;
- `src/ssi/`;
- `src/pipeline/`;
- `src/database/client.py`;
- `src/validation/`;
- `src/engine/`;
- `schema.sql` và các migration liên quan;
- `tests/`;
- `.github/workflows/`;
- các tài liệu production CLI và data pipeline.

Cần phân biệt rõ:

- **Hành vi code hiện tại**: được mô tả trong tài liệu này.
- **Schema Supabase production**: chưa thể khẳng định migration nào đã được áp dụng nếu chưa chạy schema check thực tế.
- **Dữ liệu production**: chưa thể khẳng định completeness hoặc consistency nếu chưa query Supabase.
- **SSI account thực tế**: chưa thể khẳng định mọi endpoint hoặc streaming channel đều được account hỗ trợ.
- **Test offline**: GitHub Actions `Unit Tests` đã pass trên Python 3.11 cho PR #77 ngày 18/07/2026.
- **Smoke test live**: chưa được xác nhận trong tài liệu này vì cần credential SSI/Supabase và phải mặc định read-only.

---

## Current development phase

Project đang ở:

```text
Phase 0 — Data Foundation and Validation
```

Thứ tự ưu tiên hiện tại:

1. Hiểu đúng SSI API và ý nghĩa field.
2. Raw data chính xác và có thể truy vết.
3. Clean data chính xác.
4. Completeness và consistency.
5. Feature deterministic, rerun và backfill được.
6. Signal.
7. Backtest.
8. Tối ưu chiến lược và AI.

Không dùng signal/backtest MVP hiện tại để kết luận khả năng sinh lợi.

---

## Executive status

| Thành phần | Trạng thái | Ghi chú hiện tại |
| --- | --- | --- |
| Production CLI | Implemented | Có `sync-master-data`, `init`, `daily`, `intraday-ingest`, `eod`, `features`, `intraday`, `streaming-ingest`. |
| SSI REST client | Implemented | Authentication, paging, timeout, retry `401` một lần. |
| SSI streaming client | Implemented, live chưa kiểm chứng | Classic SignalR, explicit channel, bounded timeout. |
| Master data | Implemented | `symbols`, `securities`, `indexes`, `index_components`. |
| Daily raw ingest | Implemented | `raw_daily` giữ full `DailyStockPrice` payload và hash. |
| Daily clean ingest | Implemented | `stock_daily` được validate trước khi ghi. |
| Intraday raw ingest | Partial | Có OHLCV và hash nhưng chưa giữ full source candle JSON. |
| Intraday clean ingest | Implemented | Chỉ persist `timeframe='1m'`. |
| Foreign trading | Implemented | Production daily reuse cùng `DailyStockPrice` payload, không fetch lặp. |
| Daily index | Legacy retained | Schema/data cũ được giữ; daily/EOD/backfill không còn ingest hoặc ghi `index_daily`. |
| Daily validation | Implemented | Required field, OHLC, limits, volume/value và consistency. |
| Intraday validation | Implemented | Record validation và batch validation. |
| Completeness | Partial | Daily/intraday là điều kiện chính; index/foreign/orderbook mới là count tham khảo. |
| Feature `1d` | Implemented | Nguồn từ `stock_daily`. |
| Feature intraday | Implemented | `1m`, `5m`, `15m`, `60m`; timeframe cao aggregate từ 1m. |
| Incremental feature | Implemented | Target date, warm-up và scoped upsert. |
| Full feature | Implemented, có rủi ro RAM | Toàn bộ history từng symbol vẫn được giữ trong memory. |
| Signal engine | MVP cũ, không production-ready | Feature names, check times và conflict key chưa phù hợp current contract. |
| Backtest engine | MVP/research | Dùng future bars, chưa phải T+1/T+3/T+5 trading sessions. |
| Streaming ingest | Implemented, live chưa kiểm chứng | Dry-run mặc định; raw/clean snapshot tách biệt. |
| Test offline | Passing tại mốc review | GitHub Actions Python 3.11 pass cho merge commit trước task này. |
| Alert scheduler | Not started | Chưa có production scheduler tại 09:30, 11:30, 13:30, 14:30. |
| Probability/NAV | Not started | Chưa có calibration hoặc sizing engine. |
| Production monitoring | Partial | Chưa có đầy đủ metrics, DQ history, alert failure và runbook. |

---

## Current production commands

## 1. Master-data sync

```bash
python main.py sync-master-data
python main.py init
```

`init` là alias backward-compatible.

Hiện thực hiện:

- đọc SSI `Securities`, `SecuritiesDetails`, `IndexList` và `IndexComponents`;
- ghi `symbols`, `securities`, `indexes` và `index_components`.

Không ingest history và không chạy feature/signal/backtest.

## 2. Daily ingest

```bash
python main.py daily [DD/MM/YYYY]
```

Flow hiện tại:

```text
SSI DailyStockPrice — một request cho mỗi symbol/date
    ├── raw_daily: full payload + data_hash
    ├── validate daily mapper
    └── stock_daily nếu valid, bao gồm foreign daily/room fields

Market-index daily ingest is outside the stock-only daily/EOD/backfill contract. Existing `index_daily` schema/data remains untouched.
```

`daily` chỉ đọc SSI `DailyStockPrice`, rồi ghi `raw_daily` và `stock_daily`. Pipeline không gọi `DailyIndex`, `IndexList`, `IndexComponents`, `Securities`, `SecuritiesDetails` hoặc `IntradayOhlc`; không ghi `index_daily`, `indexes`, `index_components`, `raw_intraday` hoặc `stock_intraday`; và không chạy feature/signal/backtest.

Khi không truyền ngày, command dùng `latest_previous_weekday` theo logic hiện tại. Đây là weekday-based default, chưa phải exchange holiday calendar.

Nếu `DailyStockPrice` rỗng hoặc daily validation fail, per-symbol summary trả `FAILED`; overall daily summary là `FAILED` khi tất cả symbol lỗi và `PARTIAL` khi chỉ một phần lỗi.

## 3. Intraday ingest

```bash
python main.py intraday-ingest [DD/MM/YYYY] [--symbols SSI HPG]
```

Flow hiện tại:

```text
SSI IntradayOhlc resolution=1
    ├── parse SSI local time as Asia/Ho_Chi_Minh
    ├── convert to UTC
    ├── raw_intraday
    ├── validate each clean candle
    ├── validate batch
    └── stock_intraday timeframe=1m
```

Hành vi quan trọng:

- SSI source duy nhất là `IntradayOhlc` resolution 1;
- không gọi `DailyStockPrice`, `DailyIndex` hoặc master-data endpoints;
- không ghi daily, foreign hoặc index tables;
- đọc `stock_daily` cùng symbol/date làm optional validation context từ database;
- chỉ ghi `raw_intraday` và `stock_intraday` với `timeframe='1m'`;
- thiếu daily context không chặn ingest;
- `reference_price`, `ceiling_price`, `floor_price` giữ `NULL` khi thiếu context;
- summary được đánh dấu `PARTIAL` nếu daily context thiếu;
- timestamp không parse được bị bỏ qua trước khi tạo raw/clean record;
- raw intraday được ghi trước clean validation đối với các candle parse được;
- clean candle valid vẫn được ghi ngay cả khi batch validation có warning/error; summary phản ánh `PARTIAL`;
- duplicate timestamp được deduplicate bằng cách giữ record cuối trước khi upsert clean.

## 4. EOD

```bash
python main.py eod [DD/MM/YYYY]
```

Flow hiện tại:

```text
daily ingest
    ↓
intraday-ingest 1m
    ↓
ingest completeness check
    ↓
OK / PARTIAL / FAILED
```

`eod` trả:

- `daily_summary`;
- `intraday_summary`;
- `ingest_summary`;
- `failures`;
- `warnings`;
- final `status`.

`eod` không chạy feature, signal hoặc backtest.

Khi không truyền ngày, EOD dùng `latest_weekday_on_or_before`. Nếu chạy manual trước khi phiên kết thúc vào một ngày giao dịch, có thể ingest dữ liệu chưa hoàn chỉnh. Workflow hiện chạy EOD lúc 16:30 giờ Việt Nam các ngày trong tuần.

## 5. Explicit feature pipeline

```bash
python main.py features \
  --mode incremental \
  --date DD/MM/YYYY \
  --symbols SSI HPG \
  --timeframes 1m 5m 15m 60m 1d
```

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

Feature chạy độc lập với ingest và chỉ ghi bảng `features`.

## 6. Legacy intraday feature alias

```bash
python main.py intraday --symbols SSI HPG
```

Command này:

- đọc `stock_intraday` đã có;
- chạy incremental feature;
- mặc định dùng `1m`, `5m`, `15m`;
- không ingest SSI candle;
- không tính `1d`.

Tên command là legacy compatibility alias và có thể gây hiểu nhầm nếu không đọc CLI docs.

## 7. Streaming ingest

```bash
python main.py streaming-ingest \
  --symbols SSI HPG \
  --indexes VNINDEX \
  --channels quote trade foreign-room index \
  --timeout 60 \
  --max-messages-per-channel 1
```

Hành vi hiện tại:

- yêu cầu symbol rõ ràng cho channel không phải index;
- yêu cầu index code rõ ràng cho index channel;
- timeout giới hạn từ 1 đến 3600 giây;
- message limit giới hạn từ 1 đến 1000;
- dry-run/read-only nếu không truyền `--write`;
- validate mapped record;
- giữ raw stream record riêng với validation status/issues;
- chỉ ghi clean snapshot valid khi có `--write`.

Streaming ingest không thay thế historical daily/intraday ingest và realtime bar `B` không được ghi vào canonical `stock_intraday`.

---

## Current data contracts

## 1. Master data

Các bảng chính:

```text
symbols
securities
indexes
index_components
```

Master sync là idempotent theo conflict key hiện tại và không tự chạy feature.

Điểm chưa xác minh đầy đủ:

- universe nào phù hợp cho T+;
- inactive/delisted handling;
- ETF, warrant, bond, derivative filtering;
- lịch sử thay đổi index components.

## 2. Raw daily

`raw_daily` hiện lưu:

- `symbol`;
- `trading_date`;
- `data_hash`;
- full source `payload`.

Hash được tạo từ `json.dumps(..., sort_keys=True)` nên ổn định với thứ tự key JSON thông thường.

Conflict key code sử dụng:

```text
symbol,trading_date,data_hash
```

Raw daily được ghi trước clean validation, cho phép audit source row khi clean bị reject.

## 3. Clean daily

`stock_daily` là daily source chính cho T+ và feature `1d`.

Nguồn production:

```text
SSI DailyStockPrice
```

`DailyOhlc` chỉ dùng inspector/cross-check, không thuộc production daily ingest.

Clean row chỉ được ghi khi:

- source date/symbol không mâu thuẫn request;
- mapper tạo được record;
- daily validator không có error.

Conflict key:

```text
symbol,trading_date
```

## 4. Raw intraday

`raw_intraday` hiện lưu cho mỗi candle parse được:

- `symbol`;
- UTC `time`;
- `open`, `high`, `low`, `close`;
- `volume`;
- `data_hash`.

Nguồn:

```text
SSI IntradayOhlc resolution=1
```

Conflict key code sử dụng:

```text
symbol,time,data_hash
```

Khoảng thiếu quan trọng:

- không giữ full source candle JSON;
- không giữ request params, endpoint metadata, ingest run ID hoặc mapper version;
- candle có timestamp lỗi bị bỏ qua hoàn toàn, nên raw layer không giữ được source evidence cho case đó.

## 5. Clean intraday

`stock_intraday` chỉ cho phép:

```text
timeframe = 1m
```

Database client từ chối:

- timeframe khác `1m`;
- feature columns bị ghi nhầm vào clean intraday.

Conflict key:

```text
symbol,timeframe,time
```

`stock_intraday` được partition theo tháng thông qua RPC:

```text
create_partition_if_not_exists
```

## 6. Intraday value

Công thức hiện tại:

```text
value = round(close * volume)
```

Đây là estimated candle value, không phải exact turnover từ SSI.

Nếu close hoặc volume thiếu/sai:

```text
value = NULL
```

Không tự thay missing bằng `0`.

## 7. Foreign trading

Production daily hiện reuse cùng `DailyStockPrice` payload đã lấy cho raw/clean daily.

Các field được derive gồm:

- foreign buy/sell volume;
- foreign buy/sell value;
- net volume/value;
- foreign room;
- raw source row.

Không có standalone public SSI REST `ForeignTrading` endpoint trong contract hiện tại.

Conflict key daily:

```text
symbol,trading_date
```

`stock_daily` là nguồn canonical cho foreign data cuối ngày. Production `daily` không gọi helper và không ghi row `foreign_trading`; standalone helper `fetch_foreign_trading_day` chỉ còn là compatibility path explicit.

## 8. Index data

Các bảng:

```text
indexes
index_components
index_daily
```

`index_daily` giữ raw payload cùng các field index đã map. Index code, exchange coverage và completeness thực tế vẫn cần kiểm chứng bằng SSI evidence.

## 9. Streaming raw và clean snapshots

Migration mới nhất trong repo bổ sung/reconcile:

```text
stream_raw_snapshot
stream_quote_snapshot
stream_trade_snapshot
stream_foreign_snapshot
stream_index_snapshot
stream_status_snapshot
stream_bar_snapshot
```

Raw stream record có:

- requested channel;
- payload;
- source time nếu parse được;
- `received_at`;
- payload hash;
- validation status/issues.

Clean snapshot tách theo channel type. Việc migration đã được áp dụng vào production Supabase chưa vẫn phải được schema check thực tế xác nhận.

---

## Validation and completeness

## 1. Daily validation

Daily validator kiểm tra các nhóm chính:

- required fields;
- numeric/price validity;
- volume/value không âm;
- OHLC relationship;
- floor/reference/ceiling relationship;
- price limits;
- change và percentage consistency;
- total volume/value so với match + deal khi field có đủ.

Nếu daily validation error:

- `raw_daily` vẫn giữ source payload;
- `stock_daily` không được ghi;
- production `intraday-ingest` vẫn là pipeline riêng và không bị chặn tự động bởi lỗi daily này.

## 2. Intraday record validation

Kiểm tra:

- required fields;
- timeframe `1m`;
- timezone-aware UTC timestamp;
- OHLC dương và hợp lệ;
- volume/value không âm;
- optional floor/ceiling khi context có sẵn.

## 3. Intraday batch validation

Kiểm tra:

- empty batch;
- duplicate timestamp;
- unsorted input;
- candle ngoài session;
- missing 1-minute interval;
- last intraday close so với daily close khi có context;
- tổng intraday volume so với daily matched volume khi có context.

Session rule hiện tại:

```text
09:00–11:30
13:00–15:00
Asia/Ho_Chi_Minh
```

Lunch break không được tính là missing interval.

Chưa được SSI evidence xác nhận đầy đủ:

- timestamp là bar start hay bar end;
- ATO/ATC representation;
- boundary candle tại 09:00, 11:30 và 15:00;
- khác biệt HOSE/HNX/UPCOM;
- zero-volume candle, halt và symbol ít thanh khoản.

Không dùng một con số cố định như `226` để kết luận mọi ngày đầy đủ.

## 4. Ingest completeness

Command:

```bash
python scripts/check_ingest.py --date DD/MM/YYYY
```

Hiện query:

- symbol universe;
- `stock_daily`;
- `stock_intraday` timeframe `1m`;
- `index_daily` count;
- legacy `foreign_trading` count (observability only; normal daily ingest không ghi);
- `orderbook_snapshot` count theo UTC range của ngày Việt Nam.

Per-symbol summary có:

- daily present;
- candle count;
- first/last candle;
- duplicate count;
- missing interval count;
- missing minutes;
- status.

Overall status hiện dựa chủ yếu trên:

- có hay không `stock_daily`;
- có hay không `stock_intraday`;
- missing symbol;
- duplicate/gap intraday.

Completeness chỉ đánh giá `stock_daily` và `stock_intraday` cùng missing/incomplete theo symbol. `index_daily_count` deprecated là giá trị tĩnh `0` và không query `index_daily`; các legacy observability count khác không ảnh hưởng status.

Completeness chưa bao phủ đầy đủ:

- raw-to-clean traceability;
- raw table completeness;
- field-level null rate;
- partition completeness;
- master-data completeness;
- expected index set;
- foreign field availability theo symbol;
- streaming snapshot completeness;
- holiday/non-trading-day classification.

---

## Database layer and migrations

## Code behavior đã có

- Supabase client singleton;
- bounded retry tối đa mặc định 3 lần;
- exponential backoff có jitter;
- reconnect cho lỗi auth/JWT;
- batch upsert;
- JSON sanitization;
- fail-fast khi critical table thiếu unique/exclusion constraint;
- fail-fast khi schema thiếu column;
- monthly partition handling cho `stock_intraday`.

## Conflict-key caveat

`raw_intraday` dùng:

```text
on_conflict = symbol,time,data_hash
```

Nhưng `raw_intraday` hiện không nằm trong `_CRITICAL_ON_CONFLICT_TABLES`.

Nếu production thiếu unique index tương ứng, generic database helper có thể fallback sang upsert không có explicit `on_conflict` thay vì fail-fast. Điều này cần được kiểm tra và xử lý trong task database riêng; tài liệu này không tự kết luận production đang duplicate.

## Production schema chưa được xác nhận

Cần chạy read-only schema verification để xác nhận:

- table/column/data type;
- unique index;
- migration order;
- `create_partition_if_not_exists`;
- service-role RPC permission;
- partition hiện có;
- schema drift;
- duplicate lịch sử.

Có migration trong repo không chứng minh migration đã được apply lên production.

---

## Feature pipeline

## Current contract

Một bảng feature chung:

```text
features
```

Conflict key:

```text
symbol,timeframe,time
```

Nguồn dữ liệu:

| Timeframe | Source |
| --- | --- |
| `1d` | `stock_daily` |
| `1m` | `stock_intraday` 1m |
| `5m` | aggregate từ 1m |
| `15m` | aggregate từ 1m |
| `60m` | aggregate từ 1m |

Không ghi candle aggregate ngược vào `stock_intraday`.

## Feature groups hiện có

- OHLCV và value;
- return ngắn hạn và return từ open/previous close;
- EMA9/20/50 và relationship flags;
- RSI14;
- MACD, signal, histogram;
- volume/value MA20 và ratio;
- rolling high/low và breakout flags;
- intraday VWAP và khoảng cách;
- candle range/body/position.

## Incremental mode

Hiện tải:

- target-date intraday rows;
- tối đa 300 intraday warm-up rows;
- tối đa 150 daily rows.

Feature được tính trên warm-up + target data nhưng chỉ upsert output trong target date.

Chưa có evidence đầy đủ rằng 300 rows đủ cho mọi intraday timeframe hoặc future feature.

## Full mode

Function hiện fetch paginated từ database nhưng vẫn gom toàn bộ intraday history của từng symbol vào một list/DataFrame trước khi tính.

Do đó:

- pagination chỉ giới hạn kích thước request;
- không giới hạn tổng memory mỗi symbol;
- chưa phù hợp backfill toàn universe/lịch sử lớn nếu chưa đo RAM, runtime và upsert duration.

## Chưa được chứng minh

- full và incremental tương đương trên overlapping rows;
- aggregation không vượt lunch/session boundary trong mọi case;
- aggregate timestamp đúng semantic mong muốn;
- incomplete current bar được xử lý đúng;
- formula đã đối chiếu với nguồn thứ hai;
- feature versioning;
- null behavior sau warm-up.

---

## Signal engine

Code hiện có:

```text
src/engine/signal_engine.py
src/engine/signal/
```

Strategy modules hiện gồm reversal, breakout và trend.

Signal engine hiện là MVP cũ và chưa tương thích current feature schema.

Query hiện yêu cầu:

```text
rsi
ema_20
ema_50
bb_upper
volume_spike
```

Trong khi current feature output dùng các field như:

```text
rsi14
ema20
ema50
```

`bb_upper` và `volume_spike` không có trong current feature output.

Check times trong code:

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

Signal upsert hiện dùng:

```text
symbol,signal_type,bucket_time
```

trong khi record có cả `timeframe` và `time`. Schema/migration thực tế phải được kiểm tra trước khi redesign.

Kết luận:

```text
NOT PRODUCTION READY
```

Signal không được tự động gọi sau ingest hoặc feature.

---

## Backtest engine

MVP hiện hỗ trợ:

- long/short direction;
- initial capital;
- position-size percentage;
- `holding_bars`;
- fee percentage;
- minimum score;
- skip overlapping trade cùng symbol/timeframe;
- PnL, return, win rate, max drawdown, simple Sharpe;
- in-memory test không cần Supabase.

Entry hiện dùng feature close mới nhất tại hoặc trước signal time. Exit dùng feature row sau `holding_bars`.

Đây không phải T+ backtest vì chưa xử lý:

- T+1/T+3/T+5 theo trading sessions;
- next-session execution;
- price limit và khả năng khớp lệnh;
- slippage, tax, lot size;
- liquidity;
- holiday calendar;
- missing future row;
- corporate action/adjusted price;
- portfolio-level allocation.

`run_backtest_engine` hiện load feature và signal trong cùng target date, phù hợp hơn với intraday bar MVP.

Kết luận:

```text
MVP / RESEARCH ONLY
```

---

## Streaming and order book

## Implemented

- classic ASP.NET SignalR negotiation/connection;
- explicit subscriptions;
- channel groups `F`, `X-QUOTE`, `X-TRADE`, `R`, `MI`, `B`;
- raw frame normalization;
- raw audit record;
- quote/trade/foreign/index/status/bar mapping;
- quote depth mapping đến 10 levels khi payload có field;
- validation status/issues;
- dry-run mặc định;
- clean writes chỉ khi `--write`.

## Live reliability chưa được chứng minh

- account permission;
- production channel names và field coverage;
- reconnect dài hạn;
- message loss;
- capture timestamp accuracy;
- 10-level depth availability;
- GitHub Actions stability;
- retention và snapshot cadence.

## Known loop limitation

`run_streaming_ingest` hiện dùng dictionary `latest` để đánh giá số message theo channel. Dictionary chỉ giữ một entry cho mỗi channel, nên khi `--max-messages-per-channel` lớn hơn `1`, stop condition không thật sự đếm đủ số message đã nhận theo channel và có thể chạy đến timeout dù đã nhận nhiều message.

Đây là code observation cần test/fix riêng, không phải bằng chứng live ingest đã mất dữ liệu.

Order book chưa phải dependency bắt buộc của daily pipeline Phase 0.

---

## Tests

GitHub workflow:

```text
.github/workflows/tests.yml
Python 3.11
python -m pytest -q
```

Mốc xác nhận gần nhất trước commit tài liệu này:

```text
PR #77 — Unit Tests: success — 18/07/2026
```

Test hiện bao phủ các nhóm:

- CLI contracts;
- daily/EOD/intraday-ingest pipelines;
- daily payload reuse cho raw/clean/foreign;
- one-day mapper;
- ingest completeness;
- feature engine;
- intraday value;
- backtest MVP;
- SSI REST inspector;
- SSI streaming inspector;
- streaming ingest;
- streaming migration contract;
- daily, intraday và streaming validation.

Test offline pass không chứng minh:

- production schema đúng;
- live SSI payload đúng;
- account streaming permission;
- historical completeness;
- feature full/incremental equivalence trên production data.

Các test còn cần bổ sung/củng cố:

- exact SSI sample payload fixtures có provenance;
- holiday/non-trading-day classification;
- full versus incremental feature equivalence;
- session-aware 5m/15m/60m aggregation;
- incomplete latest candle;
- partition integration;
- raw_intraday missing-constraint fail-fast;
- large pagination/memory benchmark;
- streaming count khi max messages > 1;
- T+ session-based outcomes;
- redesigned signal schema compatibility.

---

## Fixed since the previous review

Các mô tả/issue cũ sau không còn đúng với code hiện tại:

1. **`daily` ingest cả intraday** — đã tách; `daily` chỉ daily, `intraday-ingest` chỉ 1m intraday.
2. **EOD chỉ chạy daily rồi completeness** — đã sửa; EOD chạy daily → intraday → completeness.
3. **Foreign trading gọi lại `DailyStockPrice` trong production daily** — đã sửa; cùng payload được reuse.
4. **`orderbook_snapshot_count` hardcode `0`** — đã sửa; completeness query count theo time range.
5. **Intraday bị chặn khi thiếu/invalid daily context** — production intraday pipeline hiện độc lập; thiếu context được báo và optional fields giữ `NULL`.
6. **Không biết test suite pass hay fail** — GitHub Actions đã có evidence pass trên Python 3.11 tại mốc review.
7. **Không có production streaming CLI** — đã có `streaming-ingest`, bounded và dry-run mặc định.

---

## Known issues and risks

## 1. Raw intraday lineage chưa đầy đủ

Không có full source candle JSON và metadata ingest. Mức độ: **HIGH** đối với audit/remap lịch sử.

## 2. `raw_intraday` chưa nằm trong critical conflict tables

Nếu unique index thiếu, helper có thể fallback không dùng explicit conflict key. Mức độ: **HIGH** cho idempotency; cần schema check trước khi kết luận dữ liệu thực tế bị ảnh hưởng.

## 3. Completeness overall chưa dùng đầy đủ index/foreign/orderbook

Các count được query nhưng chưa quyết định overall status. Mức độ: **MEDIUM TO HIGH**.

## 4. Trading calendar chưa hoàn chỉnh

Default date và guard hiện dựa weekday; chưa có exchange holiday calendar. Mức độ: **HIGH** cho non-trading-day behavior.

## 5. Session/timestamp semantics chưa được SSI evidence xác nhận

Có nguy cơ false gap hoặc sai aggregate boundary. Mức độ: **HIGH**.

## 6. Feature reproducibility chưa được chứng minh

Warm-up, full/incremental equivalence, incomplete bar và session aggregation cần evidence. Mức độ: **HIGH**.

## 7. Full feature memory risk

Toàn bộ history từng symbol nằm trong RAM. Mức độ: **MEDIUM**.

## 8. Signal contract cũ

Feature names, check times và conflict key không phù hợp. Mức độ: **HIGH**, nhưng chưa phải ưu tiên trước Phase 0 data validation.

## 9. Backtest chưa phải T+

Future bars không tương đương T+ trading sessions. Mức độ: **HIGH** nếu dùng sai để đánh giá chiến lược.

## 10. Streaming live reliability và message-count stop condition

Implementation có nhưng live permission/reconnect/cadence chưa chứng minh; max-message counting >1 có hạn chế. Mức độ: **MEDIUM TO HIGH**.

## 11. Production schema drift

Code phụ thuộc table, column, unique index, RPC và partition. Mức độ: **HIGH** cho đến khi schema check pass.

## 12. Premature strategy conclusions

Repository có signal/backtest MVP dễ tạo cảm giác đã sẵn sàng tối ưu lợi nhuận. Thực tế project vẫn Phase 0. Mức độ: **HIGH**.

---

## Next steps

Thứ tự dưới đây bám theo Phase 0.

## Step 1 — Verify production schema read-only

Kiểm tra:

- tables/columns/data types;
- unique indexes;
- `raw_intraday` conflict key;
- partition function và partitions;
- streaming snapshot tables;
- migration application order;
- schema drift.

## Step 2 — Select verified SSI samples

Chọn ít nhất:

- một symbol thanh khoản cao, ngày giao dịch bình thường;
- một ngày nghỉ/holiday;
- một symbol ít thanh khoản;
- sample streaming nếu account hỗ trợ.

## Step 3 — Inspect SSI read-only and preserve evidence

Đối chiếu:

- `DailyStockPrice`;
- `IntradayOhlc`;
- `DailyIndex`;
- foreign fields;
- timestamp, volume, value, units;
- empty/non-trading-day behavior;
- streaming quote fields khi có.

## Step 4 — Validate raw-to-clean mapping

So sánh raw/clean theo exact symbol/date, bao gồm mismatch, `NULL`, timezone, value và rejected records.

## Step 5 — Validate completeness model

Bổ sung holiday calendar, market/session rules, zero-volume/halt handling và status rõ như `COMPLETE`, `PARTIAL`, `NO_DATA`, `NON_TRADING_DAY` nếu được chốt.

## Step 6 — Decide raw intraday lineage

Nếu thêm full payload/metadata:

- tạo migration;
- giữ backward compatibility;
- xác định dữ liệu cũ có backfill được không;
- thêm mapper/regression test.

## Step 7 — Prove feature reproducibility

So sánh full/incremental, warm-up, timeframe aggregation, lunch boundary, incomplete bar và formula output.

## Step 8 — Build operational runbook

Bao gồm schedule, explicit trading date, safe rerun, failure handling, monitoring, backfill và cleanup.

## Step 9 — Redesign signal only after Phase 0 evidence

Signal task tương lai phải dùng current feature schema, timeframe roles, alert times, versioning, reason và no-spam policy.

## Step 10 — Build session-based T+ backtest

Chỉ sau khi dữ liệu/feature được xác nhận, định nghĩa entry/exit, T+ sessions, fees/tax/slippage, price limits, liquidity và missing prices.

---

## Phase 0 exit criteria

Phase 0 chỉ hoàn thành khi có evidence cho:

### SSI contract

- endpoint/field/unit đã xác nhận;
- timestamp và volume semantics đã xác nhận;
- non-trading-day behavior đã xác nhận.

### Raw data

- daily lineage đầy đủ;
- intraday lineage được chấp nhận hoặc bổ sung;
- rerun idempotent;
- không fabricate data.

### Clean data

- daily/intraday mapper được kiểm chứng;
- timezone và `NULL` behavior đúng;
- OHLC và consistency report đáng tin.

### Completeness

- symbol/date/session-aware;
- không hardcode universal candle count;
- phân biệt trading day, non-trading day, no data và partial;
- report đủ để debug.

### Features

- `1d` từ `stock_daily`;
- intraday từ clean `1m`;
- aggregation không qua session boundary;
- full/incremental tương đương;
- không look-ahead;
- rerun/backfill được;
- formula quan trọng có test/evidence.

### Operations

- schema verified;
- migration documented/applied rõ;
- smoke test read-only;
- backfill có scope;
- failure/monitoring/runbook rõ;
- không lộ secret.

Cho đến khi các điều kiện trên đạt, project vẫn ở Phase 0.

---

## Related documents

- [Project Overview](PROJECT_OVERVIEW.md)
- [Data Pipeline](DATA_PIPELINE.md)
- [Architecture Decisions](ARCHITECTURE_DECISIONS.md)
- [CLI Usage](CLI_USAGE.md)
- [AGENTS.md](../AGENTS.md)
- [Database Schema Notes](../docs_db_schema.md)
- [Repository README](../README.md)
