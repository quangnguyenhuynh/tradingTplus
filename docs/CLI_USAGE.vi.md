# Hướng dẫn CLI TradingTPlus

[Bản tiếng Anh](CLI_USAGE.md) · Chạy từ thư mục chứa `main.py`.
Ngày và mã trong ví dụ là minh họa; thay bằng phạm vi dữ liệu của bạn.

## Bắt đầu: chọn việc cần làm

| Bạn muốn làm gì? | Lệnh nên dùng | Tác động |
| --- | --- | --- |
| Xem khối ngoại quan tâm/mua ròng/bán ròng mã nào | `foreign-rank` | Chỉ đọc RPC |
| Xem lịch sử khối ngoại của SSI | `foreign-symbol` | Chỉ đọc RPC |
| Chuẩn bị chỉ số khối ngoại | `foreign-features-preview` → `foreign-features-backfill` → `foreign-features-check` | Chỉ backfill ghi feature |
| Lấy daily cổ phiếu cuối ngày và kiểm tra | `stock-eod` | Ghi daily raw/clean |
| Lấy intraday và kiểm tra | `stock-intraday` | Ghi raw/clean 1m |
| Bổ sung daily lịch sử | `backfill-daily` | Ghi daily raw/clean |
| Tính chỉ số kỹ thuật daily | `features-daily` | Ghi stock feature 1d |
| Xem thử dữ liệu SSI VNINDEX | `index-preview` | Chỉ đọc SSI |
| Lấy daily chỉ số | `index-daily` / `index-backfill` | Ghi index raw/clean |
| Tính feature index | `index-features-daily` / `index-features-backfill` | Ghi index feature |
| Phân tích các ngày tương đồng T+ | `analogs` | Quy trình research riêng |

Không cần chạy tất cả nhóm. Để theo dõi khối ngoại, bắt đầu ở
[phần foreign](#foreign-eod). `refill` còn chạy intraday và technical features,
nên không phải bước bắt buộc để có báo cáo foreign.

## Mục lục

- [Khối ngoại: chuẩn bị, chạy và đọc kết quả](#foreign-eod)
- [Quy ước ngày, phạm vi và status](#conventions)
- [Master data](#master-data)
- [Lấy dữ liệu cổ phiếu](#stock-source)
- [Backfill và refill nguồn](#source-backfill)
- [Feature kỹ thuật cổ phiếu](#stock-features)
- [Dữ liệu và feature index](#index-data)
- [Historical Analog](#analog)
- [Streaming nâng cao](#streaming)
- [Biến môi trường](#environment)

## Cách đọc ví dụ

Khối `bash` chứa lệnh mẫu để copy sau khi thay ngày/mã.
Khối `text` có `[...]`, `DATE`, `COMMAND` là cú pháp tham khảo,
không copy nguyên dấu ngoặc. `--help` xem tham số mà không chạy pipeline:

```bash
python main.py --help
python main.py foreign-rank --help
```

<a id="foreign-eod"></a>

## Khối ngoại EOD: từ dữ liệu đến bảng xếp hạng

Phần này thống kê khối ngoại theo ngày, không chạy Analog/backtest T+.
Dữ liệu gốc nằm ở `stock_daily`; chỉ số 5/20 phiên nằm ở
`stock_foreign_features_daily`. CLI báo cáo gọi RPC chung với web/mobile.

### Chọn lệnh foreign

| Nhu cầu | Lệnh | Ghi DB? |
| --- | --- | --- |
| Tính thử một mã, một ngày | `foreign-features-preview` | Không |
| Tính và lưu cho ngày chọn | `foreign-features-daily` | Có, bảng foreign feature |
| Tính và lưu khoảng ngày | `foreign-features-backfill` | Có, bảng foreign feature |
| Tính lại để đối chiếu feature đã lưu | `foreign-features-check` | Không |
| Xem bảng xếp hạng | `foreign-rank` | Không, gọi RPC |
| Xem lịch sử một mã | `foreign-symbol` | Không, gọi RPC |

### Chuẩn bị lần đầu

1. Cài môi trường theo README gốc, chạy từ thư mục chứa `main.py`.
   Các lệnh foreign cần kết nối DB; chúng không gọi SSI.
2. Kiểm tra và chạy thủ công migration
   [20260907_create_stock_foreign_features_daily.sql](../migrations/20260907_create_stock_foreign_features_daily.sql)
   nếu chưa triển khai. File tạo bảng feature và hai RPC; CLI không tự apply.
3. Đảm bảo `stock_daily` có trường foreign và tổng giá trị giao dịch cho mã/ngày cần xem.
   Nếu thiếu, chạy riêng `backfill-daily` đúng phạm vi, rồi kiểm tra kết quả.
4. Đảm bảo `stock_daily` đã có đủ phiên giao dịch cho mã được chọn.
   Các lệnh foreign tự suy ra lịch từ các giá trị `stock_daily.trading_date` distinct trên toàn bảng,
   rồi tính từng mã được chọn theo lịch đó. Bao gồm 19 phiên trước ngày output đầu tiên nếu cần đủ feature 20D.
   Để so hai nhóm 5 phiên cần ít nhất 10 phiên nguồn.

`--calendar-file` là tùy chọn, chỉ dùng để override lịch suy ra từ `stock_daily`
khi debug hoặc chạy lại theo lịch đã xác minh thủ công. Nếu truyền file, JSON cần
`source`, `market`, `sessions`. Ví dụ cấu trúc sau chỉ minh họa:

```json
{"source":"Nguồn lịch đã được người vận hành xác minh","market":"HOSE","sessions":["2026-08-27","2026-08-28"]}
```

Ngày trong file lịch dùng `YYYY-MM-DD`; ngày trên CLI foreign dùng `DD/MM/YYYY`.
Khi dùng override, file phải chứa đầy đủ phiên thực tế, không trùng. Bộ đọc file
dựa vào xác minh của người cung cấp, chưa tự đối chiếu lịch với sàn/market của từng mã.
Nếu không truyền file, calculation dùng các ngày giao dịch có trong `stock_daily` làm lịch phiên thị trường.
Nếu `stock_daily` không có phiên nào cho scope đó, lệnh trả `PARTIAL / WINDOW_UNVERIFIED`.
`foreign-rank` và `foreign-symbol` không nhận cờ calendar.

### Chạy thử trước, rồi lưu và kiểm tra

Thay ngày/mã bằng phạm vi dữ liệu thực tế của bạn.

```bash
# 1. Chỉ tính thử SSI; chưa ghi
python main.py foreign-features-preview --symbol SSI --date 28/08/2026

# 2. Ghi feature cho khoảng ngày, khi preview đã được kiểm tra
python main.py foreign-features-backfill --from 03/08/2026 --to 28/08/2026 --symbols SSI

# 3. Đối chiếu dữ liệu nguồn với feature đã lưu
python main.py foreign-features-check --from 03/08/2026 --to 28/08/2026 --symbols SSI

# 4. Xem mua ròng 5 phiên và lịch sử SSI
python main.py foreign-rank --date 28/08/2026 --ranking accumulation --window 5 --symbols SSI --top 20
python main.py foreign-symbol --symbol SSI --date 28/08/2026 --lookback 20
```

Preview luôn in JSON; `--json` được parser chấp nhận nhưng hiện không đổi cách hiển thị.
Check trả `missing_features`, `stale` khi có kết quả tính để đối chiếu.
Đọc cả `rows[].quality_status`: `status=OK` ở summary không chứng minh mọi metric
5/20 phiên đều đủ dữ liệu. Các dòng warm-up có thể vẫn được ghi với metric NULL.

### Cập nhật một ngày hoặc tính lại

```bash
# Mặc định mode=target: chỉ ghi ngày chọn
python main.py foreign-features-daily --date 28/08/2026 --symbols SSI SHB

# Rà tối đa 20 phiên kết thúc tại ngày chọn, ghi feature mới/đổi fingerprint
python main.py foreign-features-daily --date 28/08/2026 --symbols SSI SHB --mode incremental
```

Incremental hiện chỉ rà cửa sổ tối đa 20 phiên, không quét toàn bộ lịch sử.
Sửa source cũ hơn cửa sổ này cần backfill phạm vi cụ thể.
Source ngày D thay đổi có thể ảnh hưởng D và 19 phiên kế tiếp.
Backfill chỉ ghi trong khoảng yêu cầu; xem `affected_after_range` để kiểm tra/tính lại
phần sau khoảng đó. Danh sách này lấy từ lịch suy ra hoặc lịch override.

Preview nhận một `--symbol`. Daily/backfill/check/rank nhận `--symbols SSI SHB`;
bỏ cờ này dùng danh sách active hiện tại. Không truyền cờ rỗng.
Mã unknown/inactive được service báo trong lỗi/tóm tắt; rank dùng giao với active.
Daily bắt buộc `--date`; backfill/check bắt buộc cả `--from` và `--to`,
không có alias `--from-date`/`--to-date` cho các lệnh foreign hiện tại.

### Chọn cách xếp hạng

| `--ranking` | Ý nghĩa | `--window` |
| --- | --- | --- |
| `attention` | Tổng giá trị mua + bán của khối ngoại lớn | 1, 5, 20 |
| `accumulation` | Mua ròng mạnh, số dương lớn trước | 1, 5, 20 |
| `distribution` | Bán ròng mạnh, số âm lớn về độ lớn trước | 1, 5, 20 |
| `emerging` | Mức tham gia tăng so với 5 phiên trước | Chỉ 5 |

```bash
python main.py foreign-rank --date 28/08/2026 --ranking attention --window 1 --top 20
python main.py foreign-rank --date 28/08/2026 --ranking accumulation --window 20 --sort value --top 20
python main.py foreign-rank --date 28/08/2026 --ranking distribution --window 5 --sort ratio --market HOSE --top 20
python main.py foreign-rank --date 28/08/2026 --ranking emerging --window 5 --sort ratio --top 20
python main.py foreign-rank --date 28/08/2026 --ranking attention --window 5 --top 20 --offset 20
```

- `--ranking` và `--date` bắt buộc.
- `--window` mặc định 5; `--sort` mặc định `value`, có thể chọn `ratio`.
- `--top` mặc định 20, RPC giới hạn 1..100; `--offset` mặc định 0, không âm.
- `--market` so khớp giá trị trong master; `--symbols` giới hạn thêm scope.
- `foreign-symbol --lookback` mặc định 20, RPC giới hạn 1..100.
  Đây là số dòng daily gần nhất đến ngày chọn, không phải số ngày dương lịch.
- Xếp hạng 1D không cần backfill foreign feature 20D, nhưng vẫn cần RPC đã triển khai
  và dữ liệu nguồn hợp lệ. Hạng 5/20 dùng feature đã lưu.
- `emerging --sort value` hiện cần cả feature 5D ở mốc trước trong DB;
  chỉ tính target ngày cuối có thể chưa đủ dữ liệu để trả hạng này.

### Đọc kết quả và giới hạn hiện tại

Báo cáo trả `{meta, rows}`. Xem ngày, scope, `data_status`, số mã và metric chọn
trước khi đọc hạng. Không mặc định danh sách active là toàn thị trường.

Tiền là VND. Ratio là fraction: 0.05 = 5%; change 0.02 = 2 điểm phần trăm.
Activity = mua + bán, gồm hai phía; không phải giá trị giao dịch duy nhất.
NULL là thiếu/không đủ điều kiện, không phải 0.
Các mã bằng metric có cùng hạng; phân trang sắp thêm symbol.

**Giới hạn của code hiện tại cần biết:**
- RPC chưa tính lại fingerprint từ toàn bộ source window khi truy vấn.
  `freshness=CURRENT` không chứng minh mọi source lịch sử đều chưa thay đổi.
  Check cũng chưa bao phủ đầy đủ orphan khi source target mất/không tính được.
- `eligible_count/coverage_ratio` hiện được đếm trước khi loại metric chọn bị NULL;
  có thể đánh giá độ phủ cao hơn thực tế. Không dùng coverage một mình để kết luận đủ dữ liệu.
- RPC hiện yêu cầu turnover của ngày T hợp lệ ngay cả khi sort value.
- Sửa/xóa source cần kiểm tra và tính lại đúng phạm vi trước khi sử dụng báo cáo;
  không coi những hạn chế trên đã được xử lý chỉ vì summary là OK.

### Khi lệnh chưa cho kết quả mong muốn

| Hiện tượng | Kiểm tra/làm tiếp |
| --- | --- |
| `WINDOW_UNVERIFIED` | Kiểm tra `stock_daily` có dữ liệu cho mã/range đã chọn; có thể truyền calendar override khi cần |
| `INSUFFICIENT_HISTORY`, metric NULL | Xem lịch và source warm-up; không thay NULL bằng 0 |
| `MISSING_SOURCE` trong quality | Kiểm tra source theo từng phiên; ingest bù riêng nếu cần |
| `missing_features > 0` | Backfill foreign feature đúng phạm vi rồi check lại |
| `stale > 0` | Tính lại phạm vi bị ảnh hưởng; chú ý 19 phiên sau ngày sửa |
| `rows=[]` | Kiểm tra active scope, cùng ngày, window, metric và chiều mua/bán |
| Báo thiếu table/function | Kiểm tra migration đã được triển khai đúng DB |
| RPC permission denied | Kiểm tra EXECUTE và quyền SELECT/RLS nguồn theo migration; không đưa service key vào app |

CLI dùng backend credential; chạy CLI thành công không chứng minh quyền của
web/mobile đã đúng. Migration không tự cấp toàn bộ quyền đọc nguồn cho client.
Xem [đặc tả foreign](FOREIGN_EOD_FEATURES.vi.md) để tra công thức và
[migration](../migrations/20260907_create_stock_foreign_features_daily.sql) để kiểm tra quyền.
Các giới hạn executable code nêu ở đây cần được ưu tiên khi tài liệu thiết kế mô tả mạnh hơn.

<a id="conventions"></a>

## An toàn, status và quy ước chung

- CLI cổ phiếu/foreign dùng `DD/MM/YYYY`; index còn nhận `YYYY-MM-DD`.
  Hai đầu khoảng backfill được tính vào phạm vi xử lý.
- Symbol cách nhau bằng khoảng trắng, được bỏ khoảng trắng thừa, viết hoa và loại trùng.
  Bỏ `--symbols` dùng scope mặc định của từng lệnh. Truyền cờ nhưng không có mã
  bị từ chối ở parser hoặc bước chuẩn hóa; không đồng nghĩa chạy tất cả.
  Riêng streaming: bỏ `--symbols`/`--indexes` là không đăng ký các mã đó.
- Trừ khi nói khác, command in JSON summary. Phải kiểm tra `status`: exit `0`
  gồm `OK`, `PARTIAL`, `EMPTY`, và Analog `dry_run`, `blocked`,
  `apply_requires_database`; exit `1` là `FAILED` hoặc runtime exception; exit
  `2` là lỗi parser/validation. Chỉ exit `0` không chứng minh có dữ liệu được ghi
  hay thao tác được apply.
- Ingest nguồn không tự chạy feature, signal, backtest hoặc Analog. Feature
  không tự chạy signal, backtest hoặc Analog. Không command nào tự tiến hành
  workflow Historical Analog explicit.
- Ingest cần SSI và DB; feature và báo cáo foreign chỉ cần DB.
  Không đưa credential thật vào command line hoặc tài liệu.

## Luồng kỹ thuật và Analog (khi cần)

```text
sync-master-data (hoặc init)
→ daily / intraday-ingest, hoặc stock-eod, hoặc source backfill có scope
→ kiểm tra JSON validation/completeness
→ chạy riêng features-daily và/hoặc features-intraday
→ kiểm tra feature summary
→ chỉ chạy Historical Analog trong workflow database-backed đã được duyệt
```

CLI rule cũ đã bị xóa; `analogs` là command tree Phase 1 duy nhất.

<a id="master-data"></a>

## Master data

### `sync-master-data` và alias `init`

```text
python main.py sync-master-data
python main.py init
```

Ví dụ chính là hai lệnh trên. Cả hai không có option và gọi cùng đồng bộ master
data idempotent. Chúng đọc master data SSI và ghi các bảng master được hỗ trợ;
không ingest price history, tính feature hoặc chạy signal/backtest/Analog.

<a id="stock-source"></a>

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

### `stock-eod`

```text
python main.py stock-eod [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Ví dụ: `python main.py stock-eod 07/08/2026 --symbols SSI HPG`.

- Bỏ `DATE` nghĩa là ngày trong tuần gần nhất **tính cả hôm nay** theo giờ Việt
  Nam. Điều này khác `daily`/`intraday-ingest` vốn chọn ngày trong tuần trước đó.
  Cả hai rule đều không chứng minh đó là exchange trading session.
- Bỏ `--symbols` nghĩa là toàn bộ symbol có `status=active`; cung cấp sẽ được giao với scope daily này.

Command chỉ ghi daily raw/clean và chạy daily-only completeness. Compatibility key `intraday_summary` là `null`; command không chạy intraday, index hoặc downstream.

### `stock-intraday`

```text
python main.py stock-intraday [DATE] [--symbols SYMBOL [SYMBOL ...]]
```

Chỉ lấy SSI `IntradayOhlc` resolution 1, ghi raw và source canonical 1m, rồi chạy intraday-only completeness. Không ingest daily/index hoặc chạy feature, signal, backtest, Analog. Scope automatic và explicit workflow yêu cầu cả `symbols.status='active'` và `intraday_status='active'`; mã bị loại được báo. Bỏ ngày sẽ dùng ngày trong tuần gần nhất tính cả hôm nay theo giờ Việt Nam.

<a id="source-backfill"></a>

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

<a id="stock-features"></a>

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
Bỏ `--symbols` nghĩa là mọi symbol phù hợp, trừ exact replace.
Flag không có value bị từ chối; cung cấp mã sẽ giới hạn computation. Command chỉ đọc `stock_daily`, chỉ
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

### Router tương thích `features`

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

<a id="index-data"></a>

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
  `index_daily`. Khi bỏ ngày, command dùng ngày trong tuần gần nhất bằng hoặc
  trước ngày hiện tại tại Việt Nam; vì vậy lịch `index-eod` sau giờ đóng cửa
  nhắm đúng ngày hiện tại từ thứ Hai đến thứ Sáu và thứ Sáu trước đó nếu chạy
  cuối tuần. Đây chỉ là quy tắc ngày dương lịch, không chứng minh sàn Việt Nam
  có giao dịch; ngày nghỉ và response SSI rỗng không tạo row giả.
- **Backfill:** `index-backfill` chạy source-data ingest đó cho range lịch sử
  inclusive.
- **Completeness:** `index-check` đọc database và so sánh scope index dự kiến
  với row raw và clean; command không fetch dữ liệu preview hoặc ghi row.

Với `index-daily`, `index-backfill` và `index-check`, bỏ `--indexes` sẽ lấy toàn
bộ mã có `status = 'active'` từ `index_master`. Mã explicit được kiểm tra trên
toàn bộ master và vẫn có thể chủ đích chạy một dòng inactive; mã không tồn tại
sẽ báo lỗi. Stock ingest áp dụng cùng quy tắc qua bảng `symbols`: scope bỏ trống
chỉ lấy dòng active, còn symbol explicit vẫn dùng được cho maintenance/backfill.
Pipeline index-eod độc lập chạy index ingest và stage completeness riêng. Không command nào trong
số này tính feature hoặc kết quả research.

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

<a id="analog"></a>

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

<a id="streaming"></a>

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

<a id="environment"></a>

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
