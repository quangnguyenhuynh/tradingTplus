# Feature package

Thư mục này chỉ xử lý **feature đã có dữ liệu sạch trong database**. Nó không gọi
API SSI, không ingest raw/clean data, không tạo signal, không chạy backtest và
không gửi alert.

Luồng feature luôn ghi vào một bảng duy nhất:

```text
stock_daily / stock_intraday
        |
        v
src/features
        |
        v
features(symbol, timeframe, time, ...)
```

## 1. Daily và intraday khác nhau thế nào?

| Luồng | Nguồn đọc | Timeframe ghi | Dùng để làm gì |
| --- | --- | --- | --- |
| Daily feature | `stock_daily` | `1d` | Bối cảnh chính cho T+3/T+5: xu hướng, động lượng, thanh khoản daily. |
| Intraday feature | `stock_intraday` 1m | `1m`, `5m`, `15m`, `60m` | Xác nhận và chọn thời điểm trong ngày. |

Daily và intraday đã tách execution path:

- chạy `features-daily` chỉ đọc `stock_daily`;
- chạy `features-intraday` đọc `stock_intraday` 1m và chỉ đọc thêm
  `stock_daily` để lấy official open/previous close làm context;
- 5m/15m/60m được aggregate từ 1m trong memory, không ghi ngược vào
  `stock_intraday`;
- cả hai luồng cùng ghi vào bảng `features`, phân biệt bằng cột `timeframe`.

## 2. Mỗi file làm gì?

| File | Vai trò dễ hiểu |
| --- | --- |
| `daily.py` | Luồng chạy feature daily: đọc `stock_daily`, tính `1d`, ghi `features`. |
| `intraday.py` | Luồng chạy feature intraday: đọc 1m, aggregate 5m/15m/60m, lọc bucket đã đóng, ghi `features`. |
| `common.py` | Công thức dùng chung: EMA, RSI, MACD, return, breakout, candle, nullable flag. |
| `runtime.py` | Việc kỹ thuật dùng chung: normalize date/timeframe, đọc DB có phân trang, upsert, summary. |
| `runner.py` | Router tương thích cho command cũ `features`; code mới nên gọi `daily.py` hoặc `intraday.py`. |

Hai file cũ trong `src/engine` đã bị xóa. Import mới nên dùng:

```python
from src.features.daily import run_daily_features_with_summary
from src.features.intraday import run_intraday_features_with_summary
```

## 3. Chạy feature một ngày

Chạy daily feature cho một ngày:

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI HPG
```

Ý nghĩa:

- chỉ đọc dữ liệu `stock_daily` tới ngày `10/07/2026`;
- tính lại indicator với lịch sử trước đó để đủ warm-up;
- chỉ ghi output có `timeframe = 1d` và `time` thuộc ngày target.

Chạy intraday feature cho một ngày:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m
```

Ý nghĩa:

- đọc toàn bộ 1m history có sẵn trước/tới ngày target để indicator khớp với full
  mode;
- aggregate 5m/15m/60m trong memory;
- chỉ ghi các bucket đã đóng;
- chỉ upsert output thuộc ngày target.

Khi chạy trong ngày hiện tại và muốn giả lập thời điểm alert:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --as-of 14:30 --symbols SSI
```

`--as-of 14:30` nghĩa là chỉ coi các candle đã đóng trước hoặc tại 14:30 giờ
Việt Nam là hợp lệ để ghi.

## 4. Chạy full/backfill feature

Hiện chưa có command feature dạng range riêng như:

```bash
python main.py features-intraday --from-date ... --to-date ...
```

Có hai cách chạy lại lịch sử:

### Cách A - Full mode

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 1m 5m 15m 60m
```

Full mode đọc toàn bộ dữ liệu nguồn đang có trong database và ghi lại toàn bộ
feature tương ứng. Đây là cách backfill canonical khi đã chốt công thức/schema.

Lưu ý:

- không truyền `--date` trong full mode;
- phạm vi phụ thuộc vào dữ liệu đang có trong `stock_daily`/`stock_intraday`;
- đây là database write thật vào bảng `features`;
- nên giới hạn `--symbols` khi chạy thử.

### Cách B - Incremental từng ngày

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI --timeframes 1m 5m 15m 60m
```

Cách này phù hợp để repair một ngày cụ thể. Nếu muốn repair nhiều ngày bằng
incremental thì hiện phải loop ở ngoài, ví dụ bằng shell/GitHub Actions. Repo
chưa có CLI feature range built-in.

## 5. Command cũ còn dùng được không?

Command cũ vẫn còn để tương thích:

```bash
python main.py features --mode incremental --date 10/07/2026 --symbols SSI --timeframes 1d 1m 5m 15m 60m
```

Nhưng đây là mixed router. Khi vận hành thật nên dùng command tách nguồn:

- `features-daily` cho `1d`;
- `features-intraday` cho `1m/5m/15m/60m`.

Command legacy `intraday` cũng là feature alias, không phải ingest:

```bash
python main.py intraday --symbols SSI --timeframes 1m 5m 15m
```

Muốn lấy dữ liệu SSI intraday thì dùng command khác:

```bash
python main.py intraday-ingest 10/07/2026 --symbols SSI
```

## 6. Các quy tắc correctness quan trọng

- Daily feature không tính từ intraday.
- Intraday 5m/15m/60m luôn aggregate từ clean 1m.
- Intraday chỉ ghi candle/bucket đã đóng.
- EMA/RSI/MACD intraday chạy liên tục qua các ngày quan sát, không reset mỗi
  ngày.
- `high_20_bars`/`low_20_bars` intraday nhìn các bar trước đó, tránh
  look-ahead.
- VWAP intraday reset mỗi ngày.
- `volume_ma20`/`value_ma20` intraday so với cùng bucket của 20 ngày quan sát
  trước, không lấy 20 bar trong cùng ngày.
- Boolean flag ghi `NULL` khi thiếu input, không ép thiếu dữ liệu thành `False`.
- `return_from_open` intraday dùng official `stock_daily.open_price`; thiếu
  context thì giữ `NULL`.

## 7. Value và VWAP intraday

`stock_intraday.value` hiện là ước tính:

```text
value ~= round(close * volume)
```

Vì vậy `vwap_intraday` là VWAP xấp xỉ dựa trên candle close và volume, không
phải exchange turnover VWAP chính xác từng giao dịch. Dùng được để tham khảo vị
trí giá trong ngày, nhưng không nên diễn giải như dữ liệu turnover chính xác từ
SSI.

## 8. Migration và backfill sau issue #99

Migration `20260729_drop_legacy_feature_columns.sql` xóa các cột feature legacy
không còn dùng. Migration này phải chạy thủ công sau review, không tự chạy khi
deploy code.

Sau khi deploy migration/correctness change, cần chạy lại feature để bảng
`features` đồng nhất với công thức mới:

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 1m 5m 15m 60m
```

Với production, nên chạy thử trên một vài mã trước, kiểm tra summary/output, rồi
mới mở rộng toàn bộ symbol.

## 9. Những giới hạn hiện tại

- Chưa có exchange holiday calendar tích hợp; ngày nghỉ/halt được suy từ dữ
  liệu có sẵn.
- Chưa có CLI feature backfill theo range `--from-date` / `--to-date`.
- Full mode có thể nặng vì đọc toàn bộ history có sẵn để bảo đảm indicator khớp.
- Feature command là database write, không phải smoke test read-only.
- Signal/backtest không tự chạy sau feature.
