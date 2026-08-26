# Tham chiếu CLI TradingTPlus

Đây là tài liệu đầy đủ cho cây command được đăng ký bởi `main.py`. Code runtime
là nguồn sự thật nếu tài liệu này mâu thuẫn với tài liệu thiết kế cũ. Chạy lệnh
từ thư mục gốc repo dưới dạng `python main.py ...`.

## An toàn, status và quy ước chung

- Ngày dùng `DD/MM/YYYY`. Hai đầu range backfill dữ liệu nguồn/feature đều
  inclusive.
- Option symbol nhận các giá trị cách nhau bằng khoảng trắng. Giá trị được trim,
  uppercase và deduplicate theo thứ tự xuất hiện đầu tiên. Với `--symbols` dùng
  `nargs="*"`, danh sách rỗng tường minh được normalize như scope bị bỏ qua; các
  command nguồn/feature sau đó resolve toàn bộ symbol phù hợp trong DB/master.
  Command ingest dùng `nargs="+"` sẽ từ chối `--symbols` không có giá trị.
  Streaming khác biệt: bỏ `--symbols`/`--indexes` nghĩa là danh sách rỗng, không
  bao giờ tự hiểu là `ALL`.
- Trừ khi nói khác, command in JSON summary. Phải kiểm tra `status`: exit `0`
  gồm `OK`, `PARTIAL`, `EMPTY`, và Analog `dry_run`, `blocked`,
  `apply_requires_database`; exit `1` là `FAILED` hoặc runtime exception; exit
  `2` là lỗi parser/validation. Chỉ exit `0` không chứng minh có dữ liệu được ghi
  hay thao tác được apply.
- Ingest nguồn không tự chạy feature, signal, backtest hoặc Analog. Feature
  không tự chạy signal, backtest hoặc Analog. Không command nào tự tiến hành
  workflow Historical Analog explicit.
- Command ghi dữ liệu cần access SSI/Supabase đã cấu hình. Không đưa credential
  thật vào command line hoặc tài liệu.

## Biến môi trường

`.env` được load khi import config. Credential bắt buộc không có fallback.

| Biến | Mặc định | Cách CLI sử dụng |
| --- | --- | --- |
| `SUPABASE_URL` | không có | Endpoint DB cho ingest, feature, streaming write và thao tác DB Historical Analog. |
| `SUPABASE_SERVICE_KEY` | không có | Service credential mà database client sử dụng. |
| `SUPABASE_KEY` | không có | Compatibility key được load; database client hiện dùng service key. |
| `SSI_CONSUMER_ID` | không có | Xác thực SSI REST/streaming. |
| `SSI_CONSUMER_SECRET` | không có | Xác thực SSI REST/streaming. |
| `SSI_STREAMING_BASE_URL` | `https://fc-datahub.ssi.com.vn/` | SignalR base URL cho `streaming-ingest`. |
| `SSI_SIGNALR_PATH` | `v2.0/signalr` | SignalR path. |
| `SSI_SIGNALR_HUB` | `FcMarketDataV2Hub` | Tên SignalR hub. |
| `SSI_SIGNALR_RECEIVE_METHOD` | `Broadcast` | SignalR method nhận vào. |
| `SSI_SIGNALR_SWITCH_METHOD` | `SwitchChannels` | Method đăng ký subscription. |
| `SSI_STREAMING_ENABLED` | `true` | `1`, `true`, `yes`, `y` bật streaming; giá trị khác sẽ tắt. |
| `ORDERBOOK_SNAPSHOT_TIMEOUT_SEC` | `20` | Dùng cho snapshot utility, không phải mặc định `streaming-ingest --timeout`. |
| `SSI_ORDERBOOK_URL` | không có | REST order-book account-specific tùy chọn; cây CLI này không dùng. |
| `SSI_STREAMING_URL` | không có | Placeholder tương thích ngược; không phải cấu hình kết nối SignalR. |

Các endpoint SSI REST là constant cố định trong `src/config.py`, không phải env
override. Ngày/session thị trường dùng ngữ nghĩa Asia/Ho_Chi_Minh.

## Thứ tự vận hành khuyến nghị

```text
sync-master-data (hoặc init)
→ daily / intraday-ingest, hoặc eod, hoặc source backfill có scope
→ kiểm tra JSON validation/completeness
→ chạy riêng features-daily và/hoặc features-intraday
→ kiểm tra feature summary
→ chỉ chạy Historical Analog trong workflow database-backed đã được duyệt
```

CLI rule cũ đã bị xóa; `analogs` là command tree Phase 1 duy nhất.

## Master data

### `sync-master-data` và alias `init`

```text
python main.py sync-master-data
python main.py init
```

Ví dụ chính là hai lệnh trên. Cả hai không có option và gọi cùng đồng bộ master
data idempotent. Chúng đọc master data SSI và ghi các bảng master được hỗ trợ;
không ingest price history, tính feature hoặc chạy signal/backtest/Analog.

## Ingest dữ liệu nguồn

### `daily`

```text
python main.py daily [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Ví dụ: `python main.py daily 07/08/2026 --symbols SSI HPG`.

- `DATE` là positional `DD/MM/YYYY` tùy chọn. Khi bỏ qua, dùng ngày trong tuần
  **trước đó** gần nhất theo giờ Việt Nam (không đồng nghĩa trading day đã xác
  minh).
- `--symbols` tùy chọn và cần ít nhất một giá trị nếu cung cấp. Bỏ qua nghĩa là
  toàn bộ active master symbol; cung cấp sẽ giới hạn scope.

Command đọc SSI `DailyStockPrice`, ghi `stock_raw_daily` có trace và `stock_daily`
canonical, có thể update row theo conflict key. Nó không delete dữ liệu theo
scope, không ingest intraday/index history và không chạy completeness, feature,
signal, backtest hoặc Analog.

### `intraday-ingest`

```text
python main.py intraday-ingest [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Ví dụ: `python main.py intraday-ingest 07/08/2026 --symbols SSI`. `DATE` và
`--symbols` có hành vi required/omitted giống `daily`. Command đọc SSI
`IntradayOhlc` resolution 1, ghi `stock_raw_intraday` và clean `stock_intraday` với
`timeframe='1m'`; có thể đọc `stock_daily` làm daily context. Nó không ghi nến
aggregate và không chạy daily ingest, completeness, feature, signal, backtest
hoặc Analog.

### `eod`

```text
python main.py eod [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Ví dụ: `python main.py eod 07/08/2026 --symbols SSI HPG`.

- Bỏ `DATE` nghĩa là ngày trong tuần gần nhất **tính cả hôm nay** theo giờ Việt
  Nam. Điều này khác `daily`/`intraday-ingest` vốn chọn ngày trong tuần trước đó.
  Cả hai rule đều không chứng minh đó là exchange trading session.
- Bỏ `--symbols` nghĩa là toàn bộ active master symbol; cung cấp sẽ giới hạn
  daily ingest, intraday ingest và completeness vào cùng scope.

Command ghi layer daily và 1m raw/clean, sau đó đọc để kiểm tra completeness và
trả `OK`, `PARTIAL` hoặc `FAILED`. Nó không tính feature hoặc chạy signal,
backtest, Analog.

## Backfill dữ liệu nguồn

Cú pháp chung (`--from-date`/`--to-date` là alias chính xác):

```text
python main.py COMMAND --from DD/MM/YYYY --to DD/MM/YYYY [--symbols SYMBOL [SYMBOL ...]]
python main.py COMMAND --from-date DD/MM/YYYY --to-date DD/MM/YYYY [--symbols ...]
```

`--from` và `--to` đều bắt buộc, phụ thuộc lẫn nhau và inclusive; start không
được sau end. `--symbols` tùy chọn nhưng cần ít nhất một giá trị khi xuất hiện.
Bỏ qua nghĩa là toàn bộ active master symbol; cung cấp dùng cùng scope cho mọi
ngày. Weekend được skip; response rỗng ngày trong tuần vẫn observable, không
được fabricate.

| Command | Ví dụ chính xác | Đọc/ghi |
| --- | --- | --- |
| `backfill-daily` | `python main.py backfill-daily --from 03/08/2026 --to 07/08/2026 --symbols SSI` | Chỉ ghi daily raw/clean; không intraday/completeness. |
| `backfill-intraday` | `python main.py backfill-intraday --from-date 03/08/2026 --to-date 07/08/2026 --symbols SSI` | Chỉ ghi intraday raw/clean 1m; không daily/completeness. |
| `backfill` | `python main.py backfill --from 03/08/2026 --to 07/08/2026 --symbols SSI HPG` | Chạy daily, intraday ingest và completeness cho từng ngày được tính. |

Cả ba có thể upsert source row hiện hữu; không chạy feature backfill, signal,
backtest hoặc Analog và không delete/replace theo scope.

### `refill`

```text
python main.py refill --symbol SSI --from DD/MM/YYYY --to DD/MM/YYYY
python main.py refill --symbol SSI --from-date DD/MM/YYYY --to-date DD/MM/YYYY
```

Maintenance orchestrator explicit này bắt buộc đúng một mã không rỗng, không
phải `ALL`; giá trị được trim và uppercase. Command chạy source backfill theo
thứ tự daily, intraday 1m và completeness trước khi gọi runner range feature
hiện hữu cho `1d`, `15m`, `60m`. Chỉ dùng upsert: không delete, replace, sync
master, ghi nến source aggregate, signal, backtest hay Analog. Source `PARTIAL`
vẫn chạy feature và final giữ `PARTIAL`; source `FAILED` skip feature. Hai nhánh
feature chạy độc lập. Range chỉ có cuối tuần là no-op `OK`. Exit code là `0` cho
`OK`/`PARTIAL`, `1` cho `FAILED`, `2` cho argument không hợp lệ.

## Policy dữ liệu feature và mode

`stock_features` chỉ persist `1d`, `15m`, `60m`:

| Timeframe | Nguồn canonical | Hành vi |
| --- | --- | --- |
| `1d` | `stock_daily` | Daily T+ context; không bao giờ derive từ intraday. |
| `15m`, `60m` | clean `stock_intraday` 1m | Aggregate trong memory theo session; không ghi lại nến aggregate. |

Write feature `1m`/`5m` bị từ chối. Intraday feature còn đọc `stock_daily` cho
official-open/previous-close context và chỉ persist bucket đã đóng.

- `incremental`: dùng watermark riêng theo symbol/timeframe và warm-up hữu hạn
  (5 năm cho daily; 250 source session quan sát được cho intraday). Nếu chưa có
  watermark, chỉ output trong target scope được ghi.
- range tường minh: `--from` cùng `--to` gọi feature backfill inclusive, đọc
  warm-up trước range nhưng chỉ ghi output trong range.
- `full`: đọc toàn history được chọn, tính lại và **upsert** mọi kết quả. Không
  delete row cũ và không phải replace.
- `replace` và mode alias `rebuild-clean`: tính/validate trước rồi gọi atomic RPC
  đã deploy để delete/replace một exact scope. Cần đúng một non-wildcard symbol,
  một persisted timeframe và range `--from`/`--to` hợp lệ. Chúng từ chối
  `--date` và cần atomic RPC migration đã deploy.

Incremental không thể tự phát hiện source correction cũ tùy ý nếu không có
version metadata; dùng exact replace đã review khi cần sửa lịch sử.

### `features-daily`

```text
python main.py features-daily [--mode incremental|full|replace|rebuild-clean]
  [--date DD/MM/YYYY] [--from DD/MM/YYYY --to DD/MM/YYYY]
  [--symbols [SYMBOL ...]]
```

Ví dụ:

```bash
python main.py features-daily --date 07/08/2026 --symbols SSI HPG
python main.py features-daily --from 03/08/2026 --to 07/08/2026 --symbols SSI
python main.py features-daily --mode full --symbols SSI
python main.py features-daily --mode replace --from 03/08/2026 --to 07/08/2026 --symbols SSI
```

`--mode` tùy chọn, mặc định `incremental`. Ở incremental, bắt buộc đúng một
trong `--date` hoặc cặp `--from`+`--to`; không kết hợp chúng. `full` cấm
date/range. Replace mode cần range như trên. `--from-date`/`--to-date` là alias.
Bỏ `--symbols` (hoặc flag không có value) nghĩa là mọi symbol phù hợp, trừ exact
replace; cung cấp sẽ giới hạn computation. Command chỉ đọc `stock_daily`, chỉ
ghi `stock_features` 1d và không ingest/chạy signal/backtest/Analog.

### `features-intraday`

```text
python main.py features-intraday [--mode incremental|full|replace|rebuild-clean]
  [--date DD/MM/YYYY] [--from DD/MM/YYYY --to DD/MM/YYYY]
  [--symbols [SYMBOL ...]] [--timeframes [15m 60m]] [--as-of CUTOFF]
```

Ví dụ:

```bash
python main.py features-intraday --date 07/08/2026 --symbols SSI --timeframes 15m 60m
python main.py features-intraday --date 07/08/2026 --as-of 14:30 --symbols SSI
python main.py features-intraday --mode full --symbols SSI --timeframes 60m
python main.py features-intraday --mode rebuild-clean --from 03/08/2026 --to 07/08/2026 --symbols SSI --timeframes 60m
```

Constraint date/range/mode và alias giống `features-daily`. `--timeframes` tùy
chọn, nhận nhiều value và mặc định `15m 60m`; cung cấp chỉ chọn persisted
intraday timeframe tương ứng. `--as-of` tùy chọn, nhận `HH:MM` giờ Việt Nam hoặc
timestamp timezone-aware; bỏ qua dùng mọi bucket đã đóng trong target scope.
Không kết hợp nó với range. Command đọc clean 1m, aggregate trong memory và ghi
feature row `15m`/`60m` đã đóng; không ingest, ghi nến aggregate nguồn hoặc chạy
signal/backtest/Analog.

### Router tương thích `stock_features`

```text
python main.py features [--mode incremental|full] [--date DD/MM/YYYY]
  [--symbols [SYMBOL ...]] [--timeframes [15m 60m 1d]]
```

Ví dụ: `python main.py features --date 07/08/2026 --symbols SSI --timeframes 1d 15m 60m`.
`--mode` mặc định `incremental`; `--timeframes` mặc định `15m 60m 1d`; bỏ
symbol nghĩa là mọi symbol phù hợp. `--date` là target tùy chọn cho incremental;
cung cấp sẽ giới hạn output vào ngày đó. Full tính lại/upsert history được chọn
mà không delete. Router tương thích này chỉ ghi `stock_features`; nên dùng command
source-specific cho range/replace rõ ràng. Nó không ingest/chạy
signal/backtest/Analog.

### Alias feature legacy `intraday`

```text
python main.py intraday [--snapshot-time VALUE] [--symbols [SYMBOL ...]]
  [--timeframes [15m 60m]]
```

Ví dụ: `python main.py intraday --snapshot-time 14:30 --symbols SSI --timeframes 15m`.
Bỏ symbol nghĩa là mọi symbol phù hợp; bỏ timeframe mặc định `15m 60m`.
`--snapshot-time` mặc định giờ Việt Nam hiện tại cho summary metadata; cung cấp
hiện chỉ đổi summary marker, **không** phải source/bucket cutoff an toàn. Dùng
`features-intraday --date ... --as-of ...` cho cutoff. Alias tính incremental
intraday feature; không ingest candle/chạy signal/backtest/Analog.

## Streaming ingest hữu hạn

```text
python main.py streaming-ingest [--symbols [SYMBOL ...]] [--indexes [INDEX ...]]
  --channels {securities-status,quote,trade,foreign-room,index,realtime-bar} [...]
  [--timeout SECONDS] [--max-messages-per-channel COUNT] [--write] [--debug]
```

Ví dụ read-only:

```bash
python main.py streaming-ingest --symbols SSI --indexes VNINDEX \
  --channels quote index --timeout 60 --max-messages-per-channel 1 --debug
```

`--channels` bắt buộc và nhận một hay nhiều group đã liệt kê.
`--symbols`/`--indexes` mặc định rỗng; cung cấp sẽ tạo explicit subscription đã
uppercase. Compatibility channel/scope được validate. `--timeout` mặc định `60`,
phải trong 1..3600 giây. `--max-messages-per-channel` mặc định `1`, phải trong
1..1000. `--debug` mặc định false, in sanitized summary. Không có `--write`,
command nhận/validate dữ liệu nhưng read-only; có `--write`, nó persist raw frame
và normalized snapshot row hợp lệ. Command hữu hạn và không chạy batch ingest,
feature, signal, backtest hoặc Analog.

## Runtime Historical Analog EOD V1

EOD V2 dùng cùng command với `--version 2` và exact config hash. Register rõ
ràng bằng `python main.py analogs profiles register --profile
TPLUS_ANALOG_CORE_EOD --version 2 [--apply]`. V2 vẫn draft nên
query/daily production bị chặn cho tới khi hoàn tất history, calibration, final
validation và approve riêng.

```bash
python main.py analogs profiles list
python main.py analogs profiles register [--apply]
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash <exact-hash> --symbols SSI --from DD/MM/YYYY --to DD/MM/YYYY --mode full [--apply]
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD [--apply]
python main.py analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD --distance-threshold 0.5
```

History mặc định chỉ đọc source/dry-run và chỉ persist snapshot/outcome khi có `--apply`; replace còn cần `--confirm-replace`. Query luôn đọc evidence đã persist, chỉ ghi audit với `--apply` và profile exact đã approved. Matching lấy `top_k` gần nhất; option threshold của inspect chỉ còn là input tương thích bị bỏ qua.

## Dữ liệu nguồn Index Daily

```bash
python main.py index-preview (--date DATE | --from DATE --to DATE) --indexes VNINDEX[,HNXINDEX] [--raw | --json]
python main.py index-daily [YYYY-MM-DD|DD/MM/YYYY] [--indexes VNINDEX VN30]
python main.py index-backfill --from YYYY-MM-DD|DD/MM/YYYY --to YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-check [YYYY-MM-DD|DD/MM/YYYY] [--indexes VNINDEX VN30]
python main.py index-features-preview --date YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-features-daily --date YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-features-backfill --from YYYY-MM-DD|DD/MM/YYYY --to YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
python main.py index-features-check --from YYYY-MM-DD|DD/MM/YYYY --to YYYY-MM-DD|DD/MM/YYYY [--indexes VNINDEX VN30]
```

### `index-preview` chỉ đọc

`index-preview` gọi SSI `DailyIndex`, áp dụng mapper chuẩn hóa hiện tại và in kết
quả để kiểm tra. Command không khởi tạo database client, không đọc scope trong
database và không ghi `index_raw_daily`, `index_daily` hay bất kỳ bảng raw/clean
nào. Command cũng không tính feature hoặc kết quả research.

Command nhận đúng một cách chọn ngày:

- `--date DATE` preview một ngày.
- `--from DATE --to DATE` preview mọi ngày dương lịch trong range inclusive;
  bắt buộc có `--to` khi dùng `--from`.
- Mỗi ngày nhận `YYYY-MM-DD` hoặc `DD/MM/YYYY`.
- `--indexes` là bắt buộc và nhận một giá trị phân tách bằng dấu phẩy, ví dụ
  `VNINDEX,HNXINDEX`. Khác với ingest, backfill và check, bỏ option này là lỗi
  argument; preview không lấy index code từ `index_master`.
- Mặc định in bảng dễ đọc và tóm tắt số field/field không đưa vào clean cho từng
  item SSI. `--raw` in đầy đủ row payload SSI cùng tóm tắt mapping dưới dạng
  JSON, còn `--json` in đầy đủ row clean đã chuẩn hóa (kể cả key nullable) dưới
  dạng JSON. Hai flag loại trừ nhau.

Ví dụ:

```bash
# Một ngày (cũng nhận DD/MM/YYYY)
python main.py index-preview --date 2026-08-24 --indexes VNINDEX

# Range inclusive và nhiều index
python main.py index-preview --from 2026-08-23 --to 2026-08-24 --indexes VNINDEX,HNXINDEX

# Wrapper payload SSI raw
python main.py index-preview --date 2026-08-24 --indexes VNINDEX --raw

# Chỉ các record đã chuẩn hóa
python main.py index-preview --date 24/08/2026 --indexes VNINDEX --json
```

Output mặc định có dạng sau (các giá trị chỉ để minh họa):

```text
index_code | trading_date | index_value | change | ratio_change | total_vol | total_val | source | status
----------------------------------------------------------------------------------------------------------------
VNINDEX | 2026-08-24 | 1245.5 | - | 0.25 | 123456 | - | SSI_DailyIndex | OK
```

Giá trị nguồn bị thiếu vẫn là JSON `null` và hiển thị thành `-`. Nếu SSI không
trả row, preview exit thành công và in thông báo rõ ràng như
`No SSI index daily data returned for VNINDEX on 2026-08-24`; command không tạo
row giả.

Hợp đồng raw/clean theo từng field và các alias được ghi tại
[SSI DailyIndex field mapping](SSI_DAILY_INDEX_MAPPING.md). `Time` và key source
chưa biết vẫn được giữ trong raw và được báo là không đưa vào clean; command
không âm thầm xóa hoặc tự gán ý nghĩa clean cho các field này.

Mọi đối số ngày của bốn command index nhận chính xác `YYYY-MM-DD` hoặc `DD/MM/YYYY`; ví dụ `2026-08-24` và `24/08/2026` là cùng một ngày. Separator khác như `24-08-2026` sẽ bị từ chối.

### Chọn command index

- **Preview:** `index-preview` gọi SSI và render dữ liệu raw hoặc đã chuẩn hóa;
  command không đọc hoặc ghi database.
- **Ingest ngày:** `index-daily` fetch một ngày giao dịch đã resolve, ghi bằng
  chứng payload vào `index_raw_daily`, sau đó ghi row chuẩn hóa đã validate vào
  `index_daily`.
- **Backfill:** `index-backfill` chạy source-data ingest đó cho range lịch sử
  inclusive.
- **Completeness:** `index-check` đọc database và so sánh scope index dự kiến
  với row raw và clean; command không fetch dữ liệu preview hoặc ghi row.

Với `index-daily`, `index-backfill` và `index-check`, bỏ `--indexes` sẽ lấy toàn
bộ mã chuẩn từ `index_master`; mã explicit không tồn tại sẽ báo lỗi. EOD kết hợp
index ingest với stage completeness riêng. Không command nào trong số này tính
feature hoặc kết quả research.

Quy trình khuyến nghị:

1. Chạy `index-preview` để kiểm tra response SSI.
2. Kiểm tra các field, ngày, index code và giá trị được trả về.
3. Chạy `index-daily` cho một ngày hoặc `index-backfill` cho range inclusive.
4. Chạy `index-check` để kiểm tra completeness.

### Tính index feature riêng biệt

Sau khi apply thủ công `20260826_create_index_features_daily.sql`, dùng bốn lệnh
`index-features-*` ở trên. Preview tính từ database nhưng không ghi; daily và
backfill chỉ upsert `index_features_daily`; check so sánh ngày clean hợp lệ với
feature identity và báo ngày thiếu/trùng, pre-warm-up, null bất thường sau warm-up,
raw-không-clean và lịch sử không đủ. Ingest không gọi các lệnh này và các lệnh này
không gọi ingest hoặc research downstream. Xem công thức, quy tắc null, warm-up
250 phiên và thứ tự backfill tại
[`src/index_features/README.vi.md`](../src/index_features/README.vi.md).
