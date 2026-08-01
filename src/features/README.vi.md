# Feature package

Thư mục này chỉ tính feature từ dữ liệu sạch trong database. Nó không gọi API
SSI, không ingest dữ liệu nguồn, không tạo signal, không chạy backtest và không
gửi cảnh báo.

Mọi feature được lưu chung vào một bảng:

```text
stock_daily / stock_intraday
        |
        v
src/features
        |
        v
features(symbol, timeframe, time, ...)
```

## Chính sách timeframe được lưu

Production chỉ lưu ba timeframe:

- `1d`: bối cảnh chính cho T+3/T+5, lấy từ `stock_daily`;
- `15m`: timing điểm vào và xác nhận trong phiên;
- `60m`: xác nhận intraday ở mức ổn định hơn.

`stock_intraday` vẫn phải lưu nến clean `1m`. Nến 1m là nguồn chuẩn để aggregate
15m và 60m trong memory. Các public feature runner sẽ từ chối ghi feature
`1m` và `5m` vào bảng `features`.

Cần phân biệt rõ:

```text
Nến nguồn 1m: bắt buộc lưu trong stock_intraday
Feature 1m/5m: không lưu trong features
```

Các hàm calculator/aggregate cấp thấp vẫn có thể tồn tại phục vụ nghiên cứu và
offline test, nhưng public runner qua `src.features` phải tuân thủ chính sách
production.

## Luồng daily và intraday

| Luồng | Nguồn đọc | Timeframe ghi | Mục đích |
| --- | --- | --- | --- |
| Daily feature | `stock_daily` | `1d` | Xu hướng, động lượng, thanh khoản daily và cấu trúc giá cho T+3/T+5. |
| Intraday feature | `stock_intraday` 1m cùng daily context | `15m`, `60m` | Xác nhận trong phiên và chọn thời điểm vào. |

Quy tắc:

- không tính feature daily từ intraday;
- 15m/60m luôn aggregate từ clean 1m trong memory;
- không ghi nến aggregate ngược vào `stock_intraday`;
- hai luồng cùng ghi bảng `features`;
- ingest, feature, signal và backtest vẫn là các pipeline tách biệt.

## Trách nhiệm từng file

| File | Trách nhiệm |
| --- | --- |
| `daily.py` | Đọc `stock_daily`, tính `1d`, ghi `features`. |
| `intraday.py` | Đọc clean 1m, aggregate, lọc bucket đã đóng, tính intraday feature. |
| `common.py` | Công thức và helper dataframe dùng chung. |
| `runtime.py` | Đọc DB, serialize, upsert, xử lý ngày và summary. |
| `runner.py` | Router tương thích cũ và các hàm compatibility cấp thấp. |
| `policy.py` | Default production và chặn ghi feature 1m/5m. |

Code production nên import từ `src.features`, không gọi trực tiếp
`src.features.runner` hoặc `src.features.intraday` để bỏ qua policy.

## CLI

Feature daily một ngày:

```bash
python main.py features-daily --mode incremental --date 10/07/2026 --symbols SSI HPG
```

Backfill khoảng gồm cả hai đầu (indicator dùng lịch sử trước khoảng để warm-up nhưng chỉ ghi row trong khoảng):

```bash
python main.py features-daily --from 01/07/2026 --to 29/07/2026 --symbols SSI HPG
python main.py features-intraday --from 01/07/2026 --to 29/07/2026 --symbols SSI HPG --timeframes 15m 60m
```

`--from-date` và `--to-date` vẫn là alias. `--as-of` chỉ hợp lệ với một `--date`, không dùng cho range. Các bảng nguồn chỉ được đọc; range chỉ upsert `features` và không yêu cầu backfill dữ liệu nguồn.

Feature intraday một ngày:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 15m 60m
```

Giới hạn bucket đã đóng trong ngày hiện tại:

```bash
python main.py features-intraday --mode incremental --date 10/07/2026 --as-of 14:30 --symbols SSI
```

Chạy full:

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 15m 60m
```

Full tính lại rồi upsert toàn bộ lịch sử đã chọn; không bao giờ delete trước.
Incremental lấy watermark riêng cho từng symbol/timeframe, tính với warm-up 5
năm daily hoặc 250 phiên intraday quan sát được, rồi chỉ ghi các row target. Khi
chưa có watermark, pipeline chỉ ghi ngày target được yêu cầu. `1m` và `5m` chỉ
là độ phân giải nguồn/calculator, không được persist làm feature timeframe.

`replace` / `rebuild-clean` bắt buộc đúng một symbol, một persisted timeframe và
đủ `--from`/`--to` với start không sau end. Vì chưa có backend atomic đã kiểm
chứng, command hiện fail trước mọi write/delete; không được dùng nó như cleanup
operation.

Router tương thích:

```bash
python main.py features --mode incremental --date 10/07/2026 --symbols SSI --timeframes 15m 60m 1d
```

Alias legacy:

```bash
python main.py intraday --symbols SSI --timeframes 15m 60m
```

Các command sau không hợp lệ và trả exit code `2`:

```bash
python main.py features-intraday --timeframes 1m
python main.py features-intraday --timeframes 5m
python main.py features --timeframes 1m 5m 1d
```

Muốn lấy nến nguồn 1m thì dùng:

```bash
python main.py intraday-ingest 10/07/2026 --symbols SSI
```

## Quy tắc correctness

- Intraday chỉ ghi candle/bucket đã đóng.
- EMA/RSI/MACD intraday chạy liên tục qua các ngày quan sát.
- VWAP intraday reset theo ngày.
- `volume_ma20`/`value_ma20` dùng bucket cùng giờ của các ngày quan sát trước.
- Thiếu input giữ `NULL`, không ép thành 0 hoặc `False`.
- `return_from_open` intraday dùng `stock_daily.open_price` chính thức.
- `stock_intraday.value` vẫn là giá trị ước tính `round(close * volume)`.

## Ảnh hưởng database

Thay đổi này không cần migration schema. Các row feature `1m` hoặc `5m` đã tồn
tại không bị tự động xóa. Việc xóa phải là một thao tác database riêng, có phạm
vi rõ ràng và được review trước.

Không cần backfill dữ liệu nguồn. Chỉ chạy lại feature `1d`, `15m`, `60m` khi
công thức thay đổi và cần đồng bộ lịch sử.
