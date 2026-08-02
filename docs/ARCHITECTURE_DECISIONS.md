# Architecture Decisions

## Stock-only historical ingest boundary

Phase 0 historical source ingest is stock-only. `daily` and `backfill-daily`
call SSI `DailyStockPrice` and write only `raw_daily`/`stock_daily`;
`intraday-ingest` and `backfill-intraday` call `IntradayOhlc` resolution 1 and
write only `raw_intraday`/`stock_intraday`. EOD and combined backfill compose
those stock pipelines with stock-only completeness checks. They never call
`DailyIndex`, `IndexList`, or `IndexComponents`, and never write
`index_daily`, `indexes`, or `index_components`.

Existing market-index schema and historical rows remain intact. Index master
synchronization remains an explicit responsibility of `sync-master-data` /
`init`; no replacement market-index command is introduced by this decision.

## Purpose

Tài liệu này ghi lại các quyết định kiến trúc đang áp dụng cho Trading T+.

Mục tiêu là giúp developer, ChatGPT và Codex:

- hiểu vì sao hệ thống được thiết kế như hiện tại;
- không tự ý thay đổi kiến trúc trong các task nhỏ;
- phân biệt quyết định đã chốt với vấn đề còn đang nghiên cứu;
- tránh khôi phục lại các thiết kế cũ đã bị thay thế;
- giữ data pipeline phù hợp với mục tiêu T+3 đến T+5.

Tài liệu này không thay thế:

- schema;
- migrations;
- executable code;
- tests;
- SSI specification.

Khi tài liệu và code mâu thuẫn, phải báo rõ mâu thuẫn và kiểm tra hành vi thực tế trước khi sửa.

---

## Decision Status

Các trạng thái được sử dụng:

| Status | Ý nghĩa |
|---|---|
| `Accepted` | Quyết định đã được chốt và phải tuân thủ |
| `Implemented` | Quyết định đã được chốt và phần chính đã có trong code |
| `Partially Implemented` | Đã có một phần nhưng chưa hoàn chỉnh hoặc chưa được kiểm chứng |
| `Proposed` | Phương án đang được xem xét, chưa được chốt |
| `Superseded` | Quyết định cũ đã bị thay thế |
| `Rejected` | Phương án đã được xem xét nhưng không sử dụng |
| `Deferred` | Chưa làm trong phase hiện tại |

---

## Decision Log

| ID | Quyết định | Status |
|---|---|---|
| ADR-001 | Project ưu tiên Phase 0: dữ liệu trước chiến lược | Accepted |
| ADR-002 | Tách ingest, validation, feature, signal và backtest | Implemented |
| ADR-003 | Tách raw data và clean data | Implemented |
| ADR-004 | `stock_daily` là nguồn canonical cho timeframe `1d` | Implemented |
| ADR-005 | `stock_intraday` chỉ lưu timeframe `1m` | Implemented |
| ADR-006 | `5m`, `15m`, `60m` có thể aggregate từ `1m`; production chỉ persist feature `15m`, `60m` | Implemented |
| ADR-007 | Giữ một bảng `features` có cột `timeframe` | Implemented |
| ADR-008 | Intraday value dùng `round(close * volume)` và được xem là ước tính | Implemented |
| ADR-009 | Không biến dữ liệu thiếu thành `0` nếu chưa có rule | Accepted |
| ADR-010 | Không tạo dữ liệu giả cho ngày không giao dịch hoặc API rỗng | Accepted |
| ADR-011 | Dùng giờ Việt Nam để hiểu phiên và lưu timestamp chuẩn hóa UTC | Implemented |
| ADR-012 | Mọi write pipeline phải idempotent bằng conflict key rõ ràng | Partially Implemented |
| ADR-013 | Schema change bắt buộc có migration | Accepted |
| ADR-014 | Validation phải chạy trước khi ghi clean data | Implemented |
| ADR-015 | Completeness không dựa trên một số candle cố định | Partially Implemented |
| ADR-016 | Feature phải hỗ trợ rerun, incremental và backfill | Implemented |
| ADR-017 | Không dùng dữ liệu tương lai trong feature hoặc backtest | Accepted |
| ADR-018 | Debug và smoke test mặc định read-only | Partially Implemented |
| ADR-019 | Chỉ dùng endpoint và field SSI đã được xác minh | Accepted |
| ADR-020 | Foreign trading được derive từ `DailyStockPrice` | Implemented |
| ADR-021 | Order book không được giả định có public REST endpoint | Implemented |
| ADR-022 | Signal và backtest không tự chạy sau ingest hoặc feature | Implemented |
| ADR-023 | Signal/backtest MVP legacy (đã xóa) | Superseded |
| ADR-024 | Daily context là nền chính cho quyết định T+3/T+5 | Accepted |
| ADR-025 | Alert tương lai phải ít, có lý do và không spam | Accepted |

---

# Active Decisions

## ADR-001 — Phase 0 ưu tiên dữ liệu trước chiến lược

### Status

`Accepted`

### Context

Trading T+ có mục tiêu dài hạn là tạo signal, probability, gợi ý NAV, backtest và alert.

Tuy nhiên mọi kết quả downstream đều phụ thuộc vào:

- API source;
- field meaning;
- units;
- timestamp;
- completeness;
- raw-to-clean mapping;
- feature reproducibility.

Nếu dữ liệu sai thì signal hoặc backtest có kết quả tốt cũng không có giá trị.

### Decision

Project hiện ở:

```text
Phase 0 — Data Foundation and Validation
```

Thứ tự ưu tiên bắt buộc:

1. Hiểu đúng SSI API.
2. Raw data chính xác.
3. Clean data chính xác.
4. Completeness và consistency.
5. Feature có thể rerun và backfill.
6. Signal.
7. Backtest.
8. Strategy optimization.
9. AI.

### Consequences

- Không ưu tiên tối ưu win rate.
- Không đánh giá khả năng sinh lợi từ dữ liệu chưa được xác minh.
- Không thêm AI chỉ vì đã có feature table.
- Các task Phase 0 phải ưu tiên evidence và validation.
- Signal/backtest code hiện có không được xem là production-ready.

---

## ADR-002 — Tách các pipeline theo trách nhiệm

### Status

`Implemented`

### Context

Một pipeline tự động chạy toàn bộ:

```text
ingest → feature → signal → backtest
```

sẽ gây khó khăn khi:

- API trả dữ liệu thiếu;
- mapper có lỗi;
- cần rerun một tầng;
- cần backfill;
- cần kiểm tra data trước khi tính feature;
- signal hoặc backtest có bug.

### Decision

Các tầng phải tách biệt:

1. Master-data sync
2. Daily ingest
3. Intraday ingest hoặc snapshot capture
4. Validation và completeness
5. Feature calculation
6. Signal generation
7. Backtesting
8. Alert delivery

Command hiện tại:

```text
daily   = ingest only
eod     = daily ingest + completeness
features = explicit feature computation
intraday = legacy feature alias, không ingest candle mới
```

### Consequences

- Ingest không tự động tính feature.
- EOD không tự động chạy signal/backtest.
- Feature không tự động tạo signal.
- Có thể rerun từng tầng độc lập.
- Orchestrator trong tương lai phải gọi rõ từng bước và kiểm tra status giữa các bước.

---

## ADR-003 — Tách raw data và clean data

### Status

`Implemented`

### Context

Clean data có thể thay đổi theo:

- mapper;
- validation rule;
- schema;
- cách hiểu field;
- unit normalization.

Nếu chỉ lưu clean data thì không thể kiểm tra lại source hoặc remap lịch sử.

### Decision

Raw và clean phải là hai tầng riêng.

Raw data phục vụ:

- audit;
- debug;
- source comparison;
- remapping;
- backfill;
- phát hiện SSI contract change.

Clean data phục vụ:

- validation;
- features;
- signals;
- backtests;
- application queries.

### Consequences

- Không dùng clean table thay cho raw layer.
- Không ghi feature vào clean market-data table.
- Clean row phải có thể truy ngược về source hoặc mapper rõ ràng.
- `raw_intraday` chưa lưu full source payload được ghi nhận là khoảng thiếu cần xử lý riêng.

---

## ADR-004 — `stock_daily` là nguồn canonical cho feature `1d`

### Status

`Implemented`

### Context

Daily data và intraday data có ý nghĩa khác nhau.

Tính daily feature bằng cách aggregate intraday có thể gây sai do:

- thiếu candle;
- khác source volume/value;
- auction;
- timestamp convention;
- intraday API không phản ánh đầy đủ daily source;
- deal/put-through volume.

### Decision

`stock_daily` là nguồn canonical cho:

```text
timeframe = 1d
```

Nguồn daily chính:

```text
SSI DailyStockPrice
```

`DailyOHLC` chỉ được dùng để:

- đối chiếu;
- debug;
- validation bổ sung.

Không dùng `DailyOHLC` để âm thầm thay thế `DailyStockPrice`.

### Consequences

- Feature `1d` đọc từ `stock_daily`.
- Không aggregate `stock_intraday` để tạo canonical daily bar.
- Nếu daily source thiếu thì không tự tạo daily row từ intraday.
- Daily feature backfill phụ thuộc vào `stock_daily`.

---

## ADR-005 — `stock_intraday` chỉ lưu timeframe `1m`

### Status

`Implemented`

### Context

Lưu đồng thời `1m`, `5m`, `15m`, `60m` trong clean intraday table gây:

- duplicate source-of-truth;
- khó đồng bộ khi backfill;
- tăng storage;
- dễ lệch aggregation rule;
- khó rerun khi formula thay đổi;
- nhầm clean candle với derived data.

### Decision

`stock_intraday` chỉ lưu:

```text
timeframe = 1m
```

`1m` là source of truth cho intraday clean data.

Database client phải từ chối:

- timeframe khác `1m`;
- feature columns bị ghi vào `stock_intraday`.

### Consequences

- Storage intraday đơn giản hơn.
- Higher timeframe có thể tái tạo từ source `1m`.
- Sửa aggregation rule không cần sửa clean market data.
- Mọi pipeline muốn dùng `5m`, `15m`, `60m` phải aggregate từ `1m`.

---

## ADR-006 — Aggregate higher timeframe trong feature pipeline

### Status

`Implemented`

### Context

Higher timeframe là derived data, không phải raw source trong kiến trúc hiện tại.

Nếu ghi các timeframe này vào `stock_intraday`, pipeline ingest và feature sẽ bị trộn trách nhiệm.

### Decision

Các timeframe:

```text
5m
15m
60m
```

được aggregate từ `stock_intraday` timeframe `1m` trong feature pipeline.

### Consequences

- Không ghi aggregate bar ngược vào `stock_intraday`.
- Production chỉ persist feature `15m`, `60m`; calculator `5m` không đồng
  nghĩa với việc persist feature `5m`.
- Feature pipeline chịu trách nhiệm về:
  - resampling;
  - session boundary;
  - lunch break;
  - timestamp convention;
  - incomplete bar.
- Thay đổi aggregation logic có thể yêu cầu feature backfill nhưng không yêu cầu ingest lại source data.

---

## ADR-007 — Giữ một bảng `features`

### Status

`Implemented`

### Context

Daily và intraday feature khác nguồn nhưng có thể dùng chung một storage contract:

```text
symbol
timeframe
time
feature columns
```

Tách thành nhiều bảng gây:

- duplicate schema;
- duplicate query logic;
- khó mở rộng timeframe;
- khó dùng chung signal/backtest engine;
- tăng migration và maintenance.

### Decision

Giữ một bảng:

```text
features
```

Key:

```text
symbol,timeframe,time
```

Timeframe phân biệt:

```text
1m
5m
15m
60m
1d
```

### Consequences

- Không tự ý tách thành `daily_features` và `intraday_features`.
- Feature formula phải hiểu theo timeframe của row.
- Query downstream phải luôn filter timeframe rõ ràng.
- Schema change feature áp dụng cho một bảng chung.
- Field không phù hợp với một timeframe có thể là `NULL` nếu contract cho phép.

---

## ADR-008 — Intraday value là giá trị ước tính

### Status

`Implemented`

### Context

SSI `IntradayOhlc` hiện cung cấp OHLC và volume nhưng không cung cấp exact turnover đáng tin cậy cho mỗi candle trong flow đang dùng.

### Decision

Tính:

```text
value = round(close * volume)
```

### Consequences

- Đây là estimated candle value.
- Không được mô tả là exact SSI turnover.
- Không dùng nó để khẳng định chính xác dòng tiền tuyệt đối nếu chưa kiểm chứng.
- Nếu close hoặc volume thiếu/không hợp lệ, value phải giữ `NULL`.
- Thay công thức cần:
  - giải thích source;
  - migration nếu đổi schema;
  - xác định backfill;
  - test;
  - cập nhật documentation.

---

## ADR-009 — Không tự đổi missing thành `0`

### Status

`Accepted`

### Context

`NULL` và `0` có ý nghĩa khác nhau:

- `NULL`: không biết, không có dữ liệu hoặc không được source cung cấp.
- `0`: source xác nhận giá trị bằng không.

Đổi missing thành `0` có thể làm sai:

- moving average;
- volume ratio;
- liquidity filter;
- foreign flow;
- completeness;
- backtest.

### Decision

Không thay missing value thành `0` nếu chưa có rule cụ thể cho field đó.

### Consequences

- Mapper dùng nullable values.
- Feature calculator phải xử lý `NULL` rõ ràng.
- Validation phải phân biệt missing và zero.
- Backfill không được tự điền zero để “đủ dữ liệu”.

---

## ADR-010 — Không tạo dữ liệu giả

### Status

`Accepted`

### Context

Pipeline có thể gặp:

- weekend;
- holiday;
- API trả rỗng;
- unsupported endpoint;
- symbol không giao dịch;
- account không có quyền.

Tạo fake row sẽ làm completeness nhìn có vẻ tốt nhưng dữ liệu không thật.

### Decision

Không tạo fake market data cho:

- cuối tuần;
- ngày nghỉ;
- API rỗng;
- unsupported endpoint;
- missing candle;
- missing daily response.

### Consequences

- Empty response phải được log hoặc report.
- Non-trading day phải được phân biệt với ingest failure.
- Không forward-fill OHLCV trong source/clean layer.
- Derived research dataset chỉ được fill nếu có task và rule rõ ràng.

---

## ADR-011 — Dùng giờ Việt Nam để hiểu phiên, lưu UTC

### Status

`Implemented`

### Context

SSI intraday time được hiểu trong bối cảnh thị trường Việt Nam.

Nếu lưu local naive datetime sẽ dễ xảy ra:

- sai date boundary;
- query theo ngày sai;
- aggregate sai;
- server timezone khác nhau;
- backfill không reproducible.

### Decision

- Trading session interpretation dùng:

```text
Asia/Ho_Chi_Minh
```

- Timestamp lưu trong database được chuẩn hóa sang UTC.

### Consequences

- Query theo trading date phải chuyển VN date thành UTC range.
- User-facing date/time phải convert về giờ Việt Nam.
- Timestamp không parse được phải reject, không thay bằng current time.
- Cần xác nhận timestamp SSI là bar start hay bar end.

---

## ADR-012 — Idempotent write bằng conflict key

### Status

`Partially Implemented`

### Context

Daily ingest, rerun và backfill có thể ghi cùng một dataset nhiều lần.

Không có stable key sẽ gây:

- duplicate;
- sai feature;
- sai volume;
- tăng storage;
- backtest sai.

### Decision

Mọi write pipeline phải có:

- stable conflict key;
- matching unique index;
- upsert behavior rõ ràng;
- fail-fast cho critical table nếu constraint thiếu.

Các key chính:

| Table | Conflict key |
|---|---|
| `raw_daily` | `symbol,trading_date,data_hash` |
| `stock_daily` | `symbol,trading_date` |
| `raw_intraday` | `symbol,time,data_hash` |
| `stock_intraday` | `symbol,timeframe,time` |
| `foreign_trading` | `symbol,trading_date` |
| `index_daily` | `index_code,trading_date` |
| `features` | `symbol,timeframe,time` |
| `orderbook_snapshot` | `symbol,time` |

### Consequences

- Code và database schema phải đồng nhất.
- Thêm `on_conflict` mới phải có migration/index tương ứng.
- Không fallback âm thầm nếu fallback có thể tạo duplicate ở critical table.
- Schema check phải chạy trước backfill lớn.

---

## ADR-013 — Mọi schema change phải có migration

### Status

`Accepted`

### Context

Thay đổi trực tiếp Supabase hoặc sửa code trước schema gây schema drift.

### Decision

Mọi thay đổi liên quan đến:

- table;
- column;
- type;
- constraint;
- unique index;
- partition;
- function;
- trigger;

phải có migration.

### Consequences

- Không chỉnh schema production thủ công mà không ghi lại migration.
- Migration phải được review cùng code.
- Task phải báo:
  - migration file;
  - table ảnh hưởng;
  - backfill;
  - verification SQL;
  - deployment risk.
- Không dùng README như migration source.

---

## ADR-014 — Validation trước clean persistence

### Status

`Implemented`

### Context

Raw source nên được giữ để audit, nhưng clean data phải đáp ứng contract tối thiểu.

### Decision

Flow:

```text
source
  → raw record
  → mapper
  → validation
  → clean record
```

Daily clean row chỉ được ghi nếu daily validation pass.

Clean intraday được validate độc lập; daily context là optional và nếu thiếu thì các field context giữ `NULL`/`None`, không ép về `0`.

### Consequences

- Raw có thể tồn tại dù clean bị reject.
- Validation error phải được log.
- Warning không nhất thiết chặn write.
- Không tự sửa source value để làm validation pass.
- Có thể cần quarantine/report cho rejected records trong tương lai.

---

## ADR-015 — Completeness không dùng một candle count cố định

### Status

`Partially Implemented`

### Context

Số candle có thể khác nhau do:

- source timestamp convention;
- auction;
- lunch break;
- trading halt;
- symbol ít thanh khoản;
- shortened session;
- API behavior;
- candle zero-volume có được trả hay không.

Một số như `226` không thể áp dụng cho mọi symbol và mọi ngày.

### Decision

Completeness phải dựa trên:

- symbol;
- trading date;
- exchange/session;
- first timestamp;
- last timestamp;
- duplicate;
- missing interval;
- expected-session rule;
- source behavior.

### Consequences

- Không hardcode `226` là tiêu chuẩn universal.
- Completeness report cần giải thích vì sao partial.
- Trading calendar và session model cần tiếp tục hoàn thiện.
- Đủ số candle không chứng minh field values chính xác.

---

## ADR-016 — Feature hỗ trợ rerun, incremental và backfill

### Status

`Implemented`

### Context

Feature formula có thể thay đổi và source data có thể được sửa/backfill.

Feature không thể chỉ tính một lần rồi giữ vĩnh viễn.

### Decision

Feature pipeline hỗ trợ:

- `incremental`;
- `full`;
- explicit symbol;
- explicit timeframe;
- target date;
- idempotent upsert.

### Consequences

- Ingest không gọi feature tự động.
- Incremental phải lấy warm-up history.
- Target-date rerun chỉ ghi output thuộc target date khi phù hợp.
- Full và incremental cần được so sánh trên overlapping rows.
- Formula change có thể yêu cầu feature backfill.

---

## ADR-017 — Không look-ahead

### Status

`Accepted`

### Context

Feature hoặc backtest dùng dữ liệu tương lai sẽ tạo kết quả không thể đạt được trong thực tế.

### Decision

Không dùng dữ liệu sau timestamp đang đánh giá để:

- tính feature;
- tạo signal;
- chọn entry;
- quyết định score;
- filter candidate.

### Consequences

- Live calculation chỉ dùng closed candle hoặc phải đánh dấu candle chưa đóng.
- Warm-up chỉ lấy history trước target.
- Backtest phải tách signal time và outcome time.
- Future returns không được dùng làm feature input.
- T+ outcome phải tính theo trading sessions, không phải calendar days.

---

## ADR-018 — Debug mặc định read-only

### Status

`Partially Implemented`

### Context

Debug script thường được dùng để kiểm tra API hoặc mapper.

Nếu mặc định ghi database, người dùng dễ:

- ghi nhầm ngày;
- tạo dữ liệu test;
- làm bẩn production;
- phải cleanup.

### Decision

Debug và smoke tool mặc định phải read-only.

Write phải yêu cầu:

- explicit flag;
- explicit symbol;
- explicit date;
- table scope rõ ràng;
- safety guard khi phù hợp.

### Consequences

- `--write` không được là default.
- Intraday write có thể cần flag riêng.
- Delete/update script phải giới hạn phạm vi.
- Script phải in rõ mode `READ-ONLY` hoặc `WRITE`.

---

## ADR-019 — Chỉ dùng endpoint và field SSI đã xác minh

### Status

`Accepted`

### Context

Tự suy đoán endpoint hoặc field có thể khiến code:

- gọi URL không tồn tại;
- hiểu sai payload;
- tạo dữ liệu giả;
- che giấu account permission issue.

### Decision

Chỉ dùng:

- endpoint có trong SSI documentation;
- endpoint account-specific được cấu hình rõ ràng;
- field có trong payload thật hoặc specification đã được user cung cấp.

### Consequences

- Không hardcode endpoint theo phỏng đoán.
- Unknown field phải được inspect trước khi map.
- Unsupported endpoint phải trả trạng thái rõ ràng.
- SSI specification và raw response là evidence chính.

---

## ADR-020 — Foreign trading daily thuộc canonical `stock_daily`

### Status

`Implemented`

### Context

SSI public REST specification hiện dùng trong project không có standalone `ForeignTrading` endpoint.

`DailyStockPrice` có các foreign buy/sell/net/room fields.

### Decision

Foreign trading daily được lấy từ `DailyStockPrice` và lưu trong row canonical `stock_daily`. Normal daily ingest không duplicate các giá trị này sang `foreign_trading`.

### Consequences

- Không tạo public REST URL giả cho foreign trading.
- `stock_daily` là nguồn canonical daily duy nhất, bao gồm foreign buy/sell/net/room fields.
- Foreign fields không được fetch từ standalone public REST endpoint.
- Normal daily ingest không ghi `foreign_trading`.
- Row `foreign_trading` hiện có không bị thay đổi và được giữ cho legacy compatibility/history.
- Intraday foreign streaming snapshot vẫn là dataset riêng.
- Task tương lai có thể thay legacy daily access bằng view hoặc xóa bảng cũ sau khi verify dependency.
- Không cần migration hoặc backfill vì foreign fields đã có trong `stock_daily`.

---

## ADR-021 — Order book là snapshot từ streaming hoặc endpoint riêng

### Status

`Implemented`

### Context

Public FastConnect REST list không có documented order-book endpoint trong flow đang dùng.

Quote streaming có thể cung cấp bid/ask depth fields.

### Decision

Order-book data chỉ lấy từ:

1. supported SSI streaming quote messages; hoặc
2. account-specific endpoint được cấu hình rõ ràng.

### Consequences

- Không giả định order book có thể backfill lịch sử từ REST.
- Mỗi row là point-in-time snapshot.
- Capture timestamp phải chính xác.
- Nếu unsupported thì trả `unsupported/missing`, không tạo fake depth.
- Order book chưa phải dependency bắt buộc của daily pipeline.

---

## ADR-022 — Signal và backtest không tự động chạy

### Status

`Implemented`

### Context

Signal và backtest phụ thuộc vào feature đã được xác minh.

Nếu tự động chạy sau feature, lỗi dữ liệu có thể lan xuống toàn bộ hệ thống.

### Decision

Không tự động chạy:

```text
feature → signal
signal → backtest
```

trừ khi một explicit orchestration task yêu cầu.

### Consequences

- Production CLI hiện chưa tự động gọi signal/backtest.
- Implementation tương lai phải hỗ trợ rerun bằng explicit job.
- Data issue không tự tạo hàng loạt signal sai.

---

## ADR-023 — Signal và backtest MVP legacy (đã xóa)

### Status

`Superseded`

### Context

Signal engine legacy đã dùng feature schema cũ trước khi bị xóa ngày 31/07/2026.

Backtest legacy đã dùng `holding_bars`, không phải T+3/T+5 trading sessions, và hiện đã bị xóa.

### Decision

Không còn signal/backtest executable hoặc active storage contract; thiết kế mới được deferred tới sau Phase 0.

### Consequences

- Không dùng kết quả hiện tại để quảng bá lợi nhuận.
- Không tối ưu strategy trên code MVP.
- Cần redesign signal contract sau Phase 0.
- Cần T+ session-based backtest riêng.
- Không có kết quả runtime hiện tại vì executable legacy đã bị xóa.

---

## ADR-024 — Daily context là nền chính cho T+3/T+5

### Status

`Accepted`

### Context

T+3/T+5 là horizon theo nhiều phiên, không phải vài phút.

### Decision

Vai trò timeframe:

| Timeframe | Vai trò |
|---|---|
| `1d` | Trend, momentum, liquidity, breakout và market context chính |
| `60m` | Xác nhận xu hướng và cấu trúc trong phiên |
| `15m` | Entry confirmation và momentum change |
| `5m` | Timing ngắn hạn |
| `1m` | Snapshot, execution timing và data check |

### Consequences

- Signal T+ không được dựa chủ yếu vào vài indicator `1m`.
- Daily setup nên được đánh giá trước intraday confirmation.
- Intraday không thay thế daily source.
- Backtest T+ cần outcome theo trading sessions.

---

## ADR-025 — Alert phải ít và giải thích được

### Status

`Accepted`

### Context

Cảnh báo liên tục làm giảm giá trị và khó kiểm chứng.

Mục tiêu sản phẩm là snapshot tại một số thời điểm có ý nghĩa.

### Decision

Mốc alert mục tiêu:

```text
09:30
11:30
13:30
14:30
```

Alert tương lai phải:

- có reason;
- có timeframe context;
- có suppression/deduplication;
- không gửi lại cùng một lý do liên tục;
- không được tạo chỉ vì một indicator đơn lẻ.

### Consequences

- Signal storage cần đủ dữ liệu để giải thích.
- Alert scheduler chỉ được làm sau khi signal contract rõ ràng.
- Cần phân biệt score và probability.
- Cần quy tắc no-spam trước khi production.

---

# Superseded Decisions

## SUP-001 — EOD tự động tính feature

### Status

`Superseded`

### Previous behavior or documentation

Một số đoạn README cũ mô tả:

```text
eod = daily ingest + validation + feature
```

### Replaced by

```text
eod = daily ingest + intraday ingest + completeness
features = explicit separate command
```

### Reason

Tách ingest và feature để:

- kiểm tra data trước;
- rerun độc lập;
- backfill an toàn;
- tránh lan lỗi downstream.

---

## SUP-002 — Tách `daily_features` và `intraday_features`

### Status

`Superseded`

### Previous proposal

Một số documentation cũ đề xuất tách feature thành hai bảng.

### Replaced by

Một bảng:

```text
features
```

với:

```text
symbol,timeframe,time
```

### Reason

- Tránh duplicate schema.
- Query downstream đơn giản hơn.
- Có thể thêm timeframe mà không thêm bảng.
- Đã chốt dùng một bảng có cột timeframe.

---

## SUP-003 — Tính feature `1d` từ intraday

### Status

`Superseded`

### Previous possibility

Aggregate intraday thành daily candle để tính daily indicators.

### Replaced by

```text
stock_daily → feature 1d
```

### Reason

DailyStockPrice là daily source chính và có đầy đủ daily context hơn intraday aggregate.

---

## SUP-004 — Lưu nhiều timeframe trong `stock_intraday`

### Status

`Superseded`

### Previous possibility

Lưu `1m`, `5m`, `15m`, `60m` cùng clean intraday table.

### Replaced by

```text
stock_intraday = 1m only
```

Higher timeframe được aggregate trong feature pipeline.

### Reason

- Một source of truth.
- Không duplicate derived candles.
- Backfill và rerun dễ hơn.

---

## SUP-005 — `intraday` command là intraday ingest

### Status

`Superseded`

### Previous assumption

Tên command `intraday` có thể được hiểu là lấy candle mới từ SSI.

### Current behavior

`intraday` là legacy alias cho incremental feature calculation.

### Reason

Current implementation không gọi SSI candle API.

Future intraday ingest cần command/contract riêng nếu được xây dựng.

---

## SUP-006 — Dùng `226` candle làm chuẩn completeness

### Status

`Superseded`

### Previous assumption

Một ngày đầy đủ luôn có đúng `226` candle.

### Replaced by

Session-aware, symbol-aware và date-aware completeness.

### Reason

Số candle có thể thay đổi do source behavior, auction, halt, liquidity và session convention.

---

## SUP-007 — Missing value mặc định bằng `0`

### Status

`Superseded`

### Previous behavior

Một số mapper hoặc logic cũ có thể dùng default `0` để tránh lỗi.

### Replaced by

Giữ `NULL` nếu source không cung cấp hoặc parse không hợp lệ, trừ field có rule rõ ràng.

### Reason

`0` là dữ liệu có ý nghĩa, không tương đương missing.

---

# Rejected Decisions

## REJ-001 — Tự động chạy toàn bộ pipeline sau một command

### Status

`Rejected`

### Proposal

Một command tự động:

```text
ingest → features → signal → backtest → alert
```

### Reason for rejection

- Khó kiểm soát lỗi.
- Khó rerun.
- Không phù hợp Phase 0.
- Có thể tạo signal từ dữ liệu chưa đạt completeness.
- Backfill trở nên nguy hiểm.

---

## REJ-002 — Fabricate candle để lấp gap

### Status

`Rejected`

### Proposal

Tạo candle zero-volume hoặc forward-fill giá để đủ timestamp.

### Reason for rejection

- Không còn là source data.
- Làm sai completeness.
- Làm sai indicators.
- Che giấu API/data issue.

Research transformation tương lai phải nằm ngoài raw/clean source layer.

---

## REJ-003 — Dùng order book giả hoặc endpoint đoán

### Status

`Rejected`

### Proposal

Tạo REST endpoint hoặc field order book dựa trên giả định.

### Reason for rejection

- Không có trong public specification đang dùng.
- Có thể sai account contract.
- Dữ liệu giả gây sai signal.

---

## REJ-004 — Tối ưu strategy trước khi hoàn tất data validation

### Status

`Rejected`

### Proposal

Tune RSI, EMA, signal score hoặc AI model ngay khi feature table đã có dữ liệu.

### Reason for rejection

- Input chưa được kiểm chứng.
- Dễ overfit lỗi dữ liệu.
- Backtest hiện chưa phải T+ session-based.
- Không tạo evidence đáng tin cậy.

---

# Pending Decisions

## PEND-001 — Full payload cho `raw_intraday`

### Status

`Proposed`

### Question

Có thêm full source candle JSON vào `raw_intraday` hay không?

### Cần xác minh

- Schema hiện tại.
- Storage impact.
- Migration.
- Payload size.
- Dữ liệu cũ có thể backfill không.
- Có cần source endpoint/request params không.

### Default until decided

Không tự đổi schema trong task khác.

---

## PEND-002 — Trading calendar source

### Status

`Proposed`

### Question

Nguồn nào sẽ xác định:

- trading day;
- holiday;
- shortened session;
- exchange-specific session?

### Default until decided

- Weekend guard chỉ là safety rule.
- Không xem weekday là bằng chứng chắc chắn có giao dịch.
- API response và completeness vẫn phải được kiểm tra.

---

## PEND-003 — Intraday timestamp semantics

### Status

`Proposed`

### Question

`IntradayOhlc.Time` là:

- bar start;
- bar end;
- trade bucket timestamp?

### Impact

Ảnh hưởng đến:

- missing interval;
- session boundary;
- aggregation;
- alert snapshot;
- live closed-candle rule.

### Default until decided

Không thay session/aggregation rule chỉ từ một sample.

---

## PEND-004 — Session-aware aggregation contract

### Status

`Proposed`

### Questions

- `60m` bar bắt đầu lúc nào?
- Có reset tại lunch break không?
- Có bar ngắn cuối phiên không?
- ATO/ATC được xử lý thế nào?
- Timestamp aggregate dùng start hay end?

### Default until decided

Giữ current implementation nhưng chưa tuyên bố đã được xác minh hoàn toàn.

---

## PEND-005 — Active symbol universe

### Status

`Proposed`

### Questions

Universe T+ có bao gồm:

- HOSE;
- HNX;
- UPCOM;
- DER;
- ETF;
- warrant;
- bond;
- delisted/inactive symbols?

### Impact

Ảnh hưởng đến:

- runtime;
- completeness;
- liquidity filter;
- alert noise;
- feature storage.

---

## PEND-006 — Feature versioning

### Status

`Proposed`

### Question

Có lưu:

- feature version;
- formula version;
- calculation run ID;
- source watermark;

trong `features` hoặc metadata table không?

### Impact

Cần cho reproducible research và backtest audit.

---

## PEND-007 — Signal storage contract

### Status

`Deferred`

### Questions

Cần chốt:

- signal key;
- signal type;
- timeframe;
- setup timeframe;
- confirmation timeframe;
- score;
- probability;
- reason format;
- strategy version;
- snapshot time;
- deduplication.

### Default until decided

Không tạo signal implementation mới ngoài explicit signal-design task sau Phase 0.

---

## PEND-008 — Alert snapshot contract

### Status

`Deferred`

### Questions

Tại các mốc:

```text
09:30
11:30
13:30
14:30
```

sẽ dùng:

- candle đóng gần nhất nào;
- daily context của ngày nào;
- partial current-day daily bar hay không;
- timeframe confirmation nào;
- stale-data rule nào?

---

## PEND-009 — T+ backtest execution model

### Status

`Deferred`

### Questions

Cần chốt:

- entry tại snapshot close hay next open;
- T+3/T+5 tính theo trading sessions;
- exit price;
- fee;
- tax;
- slippage;
- price limit;
- liquidity;
- missing price;
- corporate action;
- overlapping signal;
- portfolio capital allocation.

### Default until decided

MVP `holding_bars` đã bị xóa; không có T+ backtest chính thức.

---

## PEND-010 — Probability và NAV sizing

### Status

`Deferred`

### Questions

- Score chuyển thành probability bằng cách nào?
- Probability được calibrate ra sao?
- NAV suggestion phụ thuộc:
  - confidence;
  - liquidity;
  - volatility;
  - drawdown;
  - market regime;
  - current portfolio exposure;
  như thế nào?

### Default until decided

Không đưa ra phần trăm NAV tự động.

---

## PEND-011 — Order-book retention và cadence

### Status

`Deferred`

### Questions

- Lưu snapshot ở mốc alert hay liên tục?
- Bao nhiêu level?
- Retention bao lâu?
- Có cần raw streaming messages không?
- Order book có đủ giá trị cho T+3/T+5 không?
- GitHub Actions có phù hợp để capture live stream không?

---

## PEND-012 — Completeness status model

### Status

`Proposed`

### Question

Có cần chuẩn hóa status thành:

```text
COMPLETE
PARTIAL
FAILED
NON_TRADING_DAY
NO_DATA
UNSUPPORTED
```

thay cho chỉ:

```text
OK
PARTIAL
FAILED
```

### Impact

Giúp phân biệt:

- ngày nghỉ;
- API failure;
- source unsupported;
- symbol không giao dịch;
- dữ liệu thiếu.

---

# Architectural Guardrails

Mọi task phải tuân thủ các guardrail sau.

## Data

- Không fabricate market data.
- Không đổi missing thành zero khi chưa có rule.
- Không tính canonical `1d` từ intraday.
- Không lưu higher timeframe vào `stock_intraday`.
- Không ghi feature columns vào clean source tables.
- Không hardcode universal candle count.
- Không tự tạo endpoint SSI.

## Pipeline

- Ingest không tự động tính feature.
- Feature không tự động tạo signal.
- Signal không tự động chạy backtest.
- Daily và intraday phải tách contract.
- Raw và clean phải tách tầng.
- Rerun/backfill phải idempotent.

## Database

- Schema change phải có migration.
- Conflict key phải có unique constraint.
- Không xóa production data nếu chưa chứng minh cần thiết.
- Backfill phải có symbol/date scope.
- Partition change phải có verification.

## Features

- Một bảng `features`.
- Timeframe là một phần của key.
- Incremental phải có warm-up.
- Không look-ahead.
- Không dùng incomplete candle như closed candle.
- Formula change phải xác định backfill.

## Signal và backtest

- Không đánh giá profitability từ dữ liệu chưa được xác minh.
- Signal phải explainable.
- Alert phải ít và không spam.
- T+ outcome phải theo trading sessions.
- Current MVP không phải production strategy.

## Operations

- Debug mặc định read-only.
- Write cần explicit scope.
- Retry có giới hạn.
- Không nuốt exception.
- Không in secret hoặc token.
- Không báo hoàn thành khi test chưa chạy hoặc còn lỗi.

---

# Decision Change Process

Một quyết định kiến trúc chỉ được thay đổi khi task có đầy đủ:

1. Vấn đề hiện tại.
2. Evidence từ code/data/API.
3. Quyết định cũ bị ảnh hưởng.
4. Phương án mới.
5. Alternative đã xem xét.
6. Schema impact.
7. Migration.
8. Data impact.
9. Backfill.
10. Backward compatibility.
11. Test plan.
12. Rollout plan.
13. Documentation update.

Không thay đổi kiến trúc như một phần phụ của bug fix nhỏ.

Khi thay đổi một ADR:

- giữ lại ADR cũ;
- đổi status thành `Superseded`;
- ghi ADR mới;
- liên kết hai quyết định;
- cập nhật `CURRENT_STATE.md`;
- cập nhật `DATA_PIPELINE.md`;
- cập nhật README nếu có nội dung liên quan.

---

# Decision Template

Dùng template sau khi thêm quyết định mới.

```markdown
## ADR-XXX — Tên quyết định

### Status

`Proposed | Accepted | Implemented | Partially Implemented | Superseded | Rejected | Deferred`

### Date

`YYYY-MM-DD`

### Context

Mô tả:

- vấn đề;
- hiện trạng;
- constraint;
- evidence;
- lý do cần quyết định.

### Decision

Mô tả quyết định đã chọn.

### Alternatives Considered

#### Alternative 1

Mô tả phương án và lý do không chọn.

#### Alternative 2

Mô tả phương án và lý do không chọn.

### Consequences

#### Positive

- Lợi ích.

#### Negative

- Trade-off hoặc chi phí.

### Database Impact

- Migration: `none` hoặc tên migration.
- Tables affected.
- Backfill required hay không.

### Compatibility

- CLI impact.
- Public function impact.
- Schema impact.
- Existing-data impact.

### Validation

- Tests.
- Smoke checks.
- Verification queries.

### Related Decisions

- ADR liên quan.
```

---

# Related Documents

- [Project Overview](PROJECT_OVERVIEW.md)
- [Current State](CURRENT_STATE.md)
- [Data Pipeline](DATA_PIPELINE.md)
- [AGENTS.md](../AGENTS.md)
- [Schema snapshot](../schema.sql)
- [Database migrations](../migrations/README.md)
- [README](../README.md)
---

## ADR-002 update: production daily/intraday split

Status: accepted for Phase 0.

Decision: production daily ingest and production intraday ingest are separate commands and public entry functions.

Consequences:

- `python main.py daily [DD/MM/YYYY]` must not call SSI `IntradayOhlc` and must not write `raw_intraday` or `stock_intraday`.
- `python main.py intraday-ingest [DD/MM/YYYY] [--symbols ...]` must call SSI `IntradayOhlc` resolution `1` and write only `raw_intraday` and `stock_intraday` for candle ingest.
- `python main.py eod [DD/MM/YYYY]` is an orchestrator: daily ingest → intraday ingest → completeness check.
- `python main.py intraday` remains a backward-compatible feature alias and must not be redefined as an ingest command.
- Feature computation, signal generation, and backtesting remain explicit downstream stages.

No schema change is required for this split.

> Feature execution update (issue #99): implementation is owned by `src/features/`. Use source-isolated `features-daily` and `features-intraday`; `features` and `intraday` are compatibility routes. Intraday persistence uses closed buckets, official daily open, continuous indicators/high-low, same-bucket prior-20-observed-date volume/value baselines, and nullable flags. See `src/features/README.md`.

## ADR-020 — Scoped feature replacement is one atomic RPC

### Status
Implemented in code and migration; production deployment of the 2026-08-02 migration remains an operator action.

### Decision
`full` is a non-destructive upsert. `replace`/`rebuild-clean` accepts one exact symbol, one persisted timeframe, and inclusive Vietnam dates, computes and validates all replacement rows before mutation, and calls `public.replace_features_atomic` once with a half-open UTC range. The service-role-only function validates again, deletes only that range, inserts all rows in the same transaction, and never falls back to application delete/upsert.
