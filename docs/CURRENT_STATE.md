# Current State

## Document status

Tài liệu này mô tả trạng thái hiện tại của repository Trading T+ dựa trên code, migration, test và workflow đang có.

Last reviewed against repository code:

```text
06/08/2026
```

Mốc repository dùng để đối chiếu:

```text
dev tại `51da9d4`, cộng branch tài liệu Phase 1 hiện tại
```

Phạm vi đã đọc và đối chiếu gồm:

- `main.py`;
- `src/ssi/`;
- `src/pipeline/`;
- `src/database/client.py`;
- `src/validation/`;
- `src/features/`;
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
Phase 0 — COMPLETE_WITH_NOTES
Phase 1 — historical analog design accepted; implementation not started
```

Thứ tự ưu tiên hiện tại:

1. Hiểu đúng SSI API và ý nghĩa field.
2. Raw data chính xác và có thể truy vết.
3. Clean data chính xác.
4. Completeness và consistency.
5. Feature deterministic, rerun và backfill được.
6. Historical analog cùng mã/cùng checkpoint.
7. Validation phương pháp theo thời gian.
8. Signal/ranking/%NAV và AI ở phase sau.

Repo hiện có fixed-rule strategy/signal/backtest executable từ PR #121/#123,
nhưng luồng này đã bị thay thế và đang đóng băng. Thiết kế Phase 1 được chấp nhận
là historical analog cùng mã/cùng checkpoint; schema/pipeline/CLI mới chưa có.

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
| Feature intraday | Implemented | Chỉ persist `15m`, `60m`; cả hai aggregate từ clean 1m trong memory. |
| Incremental feature | Implemented | Target date, warm-up và scoped upsert. |
| Full feature | Implemented, có rủi ro RAM | Toàn bộ history từng symbol vẫn được giữ trong memory. |
| Fixed-rule strategy/signal/backtest | Implemented, dormant/superseded | Code, CLI, schema, migrations và test còn tồn tại; không dùng production hoặc làm evidence cho hướng mới. |
| Historical analog Phase 1 | Design accepted, not implemented | Cùng mã/cùng checkpoint; thiếu mẫu trả `insufficient_sample`. |
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
  --timeframes 15m 60m 1d
```

Supported modes:

```text
incremental
full
replace / rebuild-clean (atomic exact-scope RPC; new migration requires operator deployment)
```

Supported timeframes:

```text
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
- mặc định chỉ persist `15m`, `60m`;
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
- `data_hash`;
- nullable `payload JSONB` chứa toàn bộ object candle SSI cho ingest mới.

Nguồn:

```text
SSI IntradayOhlc resolution=1
```

Conflict key code sử dụng:

```text
symbol,time,data_hash
```

Khoảng thiếu quan trọng:

- row lịch sử trước migration có thể có `payload = NULL` và task này không backfill;
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

`ref_price`, `ceiling_price` và `floor_price` là price context nullable: field thiếu hoặc placeholder `0` từ SSI được lưu `NULL` ở clean row và các check phụ thuộc được bỏ qua. Khi đủ context, dải OHLC đồng nhất nằm hoàn toàn cùng một phía ngoài source limits được báo warning để giữ row corporate action; vi phạm limit đơn lẻ và lỗi OHLC thực sự sai vẫn blocking. Raw payload không bị sửa.

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

`raw_intraday` nằm trong `_CRITICAL_ON_CONFLICT_TABLES`; nếu production thiếu
unique index tương ứng, ingest fail-fast thay vì fallback sang upsert không có
explicit conflict key.

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

Daily và intraday đã có execution path riêng:

- daily chỉ đọc `stock_daily`;
- intraday đọc `stock_intraday(timeframe='1m')` và daily context;
- đọc watermark riêng theo symbol/timeframe;
- daily dùng warm-up 5 năm, intraday dùng mặc định 250 phiên giao dịch quan sát
  được (cấu hình hợp lệ 200-250), thay vì bắt buộc đọc toàn bộ history;
- chỉ output sau watermark đến target date được upsert; nếu chưa có watermark,
  chỉ output target date được ghi;
- intraday chỉ ghi bucket đã đóng theo cutoff Việt Nam.

Full vẫn đọc toàn history; incremental dùng warm-up bounded để giảm query/RAM.

Replace/rebuild-clean bắt buộc đúng một symbol, một persisted timeframe và đủ
start/end. Implementation compute và validate toàn bộ replacement trước khi gọi đúng một transaction/RPC atomic theo exact scope; migration mới cần operator deploy trước khi dùng.

## Full mode

Function hiện fetch paginated từ database nhưng vẫn gom toàn bộ intraday history
của từng symbol vào một list/DataFrame trước khi tính.

Do đó:

- pagination chỉ giới hạn kích thước request;
- không giới hạn tổng memory mỗi symbol;
- chưa phù hợp backfill toàn universe/lịch sử lớn nếu chưa đo RAM, runtime và upsert duration.

## Kiểm chứng và giới hạn còn lại

Offline test hiện kiểm tra parity daily và persisted intraday giữa execution
full/incremental trên dataset xác định, boundary 250 phiên warm-up, watermark,
không vượt lunch/date boundary, nullable flag, closed bucket và các hằng số
RSI/MACD độc lập. Vẫn còn cần kiểm chứng production/read-only đối với:

- session/holiday/halt thực tế;
- độ đầy đủ daily context;
- performance all-history trên toàn universe;
- feature versioning;
- đối chiếu thêm EMA/RSI/MACD với nguồn thị trường thứ hai.

---

## Signal and backtest status

The original pre-Phase-0 signal/backtest MVP was removed, but PR #121/#123 later
added a new executable fixed-rule strategy/signal/backtest research path with
CLI, six storage tables, migrations, and offline tests. That newer path remains
in the repository but is dormant/superseded and is not production-approved.

The accepted target is the same-symbol/same-checkpoint historical-analog method
in [`phase1/HISTORICAL_ANALOG_SPEC.md`](phase1/HISTORICAL_ANALOG_SPEC.md). Its
schema, pipeline, CLI, and runtime are not implemented. Feature execution does
not trigger either the dormant fixed-rule path or future analog research.

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
- full versus incremental equivalence trên dữ liệu production đủ dài;
- session-aware 5m/15m/60m aggregation;
- incomplete latest candle;
- partition integration;
- large pagination/memory benchmark;
- streaming count khi max messages > 1;
- future T+ session-based outcome contract tests;
- future redesigned signal schema contract tests.

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

## 1. Raw intraday lineage lịch sử chưa đầy đủ

Ingest mới giữ full source candle JSON, nhưng row lịch sử có thể `NULL` và vẫn
chưa có request/run/mapper-version metadata. Không có backfill trong task này.

## 2. Production schema cần read-only verification

Code đã fail-fast conflict key, nhưng vẫn cần xác nhận migration payload và
unique index thực tế trên linked project trước khi coi deployment hoàn tất.

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

## 8. Signal contract deferred

Không có implementation hoặc storage contract active. Việc thiết kế sớm trước
khi data/feature được kiểm chứng có mức rủi ro **HIGH**.

## 9. Backtest contract deferred

Không có implementation hoặc storage contract active. Thiết kế tương lai phải
dùng trading sessions; mức rủi ro **HIGH** nếu dùng calendar/bar count thay thế.

## 10. Streaming live reliability và message-count stop condition

Implementation có nhưng live permission/reconnect/cadence chưa chứng minh; max-message counting >1 có hạn chế. Mức độ: **MEDIUM TO HIGH**.

## 11. Production schema drift

Code phụ thuộc table, column, unique index, RPC và partition. Mức độ: **HIGH** cho đến khi schema check pass.

## 12. Premature strategy conclusions

Repository không có signal/backtest executable; thiết kế tương lai vẫn có rủi ro bị bắt đầu quá sớm. Thực tế project vẫn Phase 0. Mức độ: **HIGH**.

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

Phase 0 đã được owner đóng `COMPLETE_WITH_NOTES`; các rủi ro còn lại tiếp tục
được theo dõi theo báo cáo Phase 0 và không được che bằng dữ liệu giả.

---

## Related documents

- [Project Overview](PROJECT_OVERVIEW.md)
- [Data Pipeline](DATA_PIPELINE.md)
- [Architecture Decisions](ARCHITECTURE_DECISIONS.md)
- [CLI Usage](CLI_USAGE.md)
- [AGENTS.md](../AGENTS.md)
- [Schema snapshot](../schema.sql)
- [Database migrations](../migrations/README.md)
- [Repository README](../README.md)
# Application write clocks (2026-07-24)

Primary daily, intraday, master-data, optional foreign/order-book, streaming,
feature, and data-quality write paths stamp persistence timestamps in application
code with timezone-aware `Asia/Ho_Chi_Minh` values carrying an explicit `+07:00`
offset. PostgreSQL `now()` defaults are removed for these audit fields. The database client uses a preserve-safe
insert-ignore/update sequence so upsert reruns do not reset existing `created_at`.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.

## Issue #110 Phase 0 closure review (updated 2026-08-03)

The reviewed repository commit is `f80244bb350d3876762532241e372e0f0d2d1f71`
plus the closure-gate changes described in
`docs/phase0/PHASE0_VALIDATION_REPORT.md`. The owner reports that the two closure
migrations were manually applied through Supabase SQL Editor and that the
expected production schema was verified read-only. This is
`PASS_WITH_MANUAL_APPLY_NOTE`; CLI migration history may not reflect the apply.

Daily feature reads now paginate `stock_daily`; incremental daily retains a five-year warm-up. Intraday incremental retains 250 observed trading sessions (configurable 200–250), not calendar days/bars. Full remains non-destructive; incremental no-output is an `OK` no-op; scoped replace computes and validates before one atomic service-role RPC. Historical corrections are not automatically detected without source-version metadata, so operators must request exact scoped replace/full work separately.

New intraday ingest rows now preserve the complete semantic SSI candle object in
nullable `raw_intraday.payload JSONB`; historical rows may remain `NULL` and no
payload backfill occurred. The owner also verified scoped SSI/raw/clean/feature
samples without unexplained critical mismatch. The authoritative/versioned
exchange calendar and exact retained sample identifiers remain documented
risks, not reasons to fabricate evidence. Phase 0 is **COMPLETE_WITH_NOTES**;
the accepted historical-analog Phase 1 implementation is not present.

### Dormant fixed-rule CLI and accepted Phase 1 direction (2026-08-06)

`strategies` and `signals` commands are executable research artifacts, but their
fixed-rule flow is superseded and must not be used as the production Phase 1
path. The accepted target is documented in
[`phase1/HISTORICAL_ANALOG_SPEC.md`](phase1/HISTORICAL_ANALOG_SPEC.md):
same-symbol/same-checkpoint matching, H+1/H+3/H+5 distributions,
chronological validation, and read-only analysis. Its CLI/schema do not exist.
