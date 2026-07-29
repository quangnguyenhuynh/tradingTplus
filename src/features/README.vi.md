# Feature package

Thư mục này chỉ tính feature từ dữ liệu sạch trong database. Nó không gọi API SSI, không ingest dữ liệu nguồn, không tạo signal, không chạy backtest và không gửi cảnh báo.

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

Production chỉ lưu:

- `1d` từ `stock_daily`;
- `15m` và `60m` được aggregate trong memory từ nến clean `stock_intraday` 1m.

Feature `1m` và `5m` bị từ chối ghi. Nến nguồn chuẩn `1m` vẫn được lưu trong `stock_intraday`.

## Trách nhiệm từng file

| File | Trách nhiệm |
| --- | --- |
| `daily.py` | Đọc `stock_daily`, tính `1d`, ghi `features`. |
| `intraday.py` | Đọc clean 1m, aggregate bucket 15m/60m đã đóng và tính intraday feature. |
| `backfill.py` | Tính lại feature theo khoảng ngày, có warm-up từ lịch sử trước đó và chỉ ghi phần nằm trong khoảng yêu cầu. |
| `common.py` | Công thức và helper dataframe dùng chung. |
| `runtime.py` | Đọc DB, serialize, upsert, xử lý ngày và summary. |
| `runner.py` | Router tương thích và các hàm compatibility cấp thấp. |
| `policy.py` | Default production và validation timeframe được phép lưu. |

Code production nên import từ `src.features`.

## Các phạm vi chạy CLI

Mỗi lần chạy command feature chỉ được chọn một phạm vi.

### Một ngày cụ thể

```bash
python main.py features-daily --date 10/07/2026 --symbols SSI HPG
python main.py features-intraday --date 10/07/2026 --symbols SSI HPG --timeframes 15m 60m
```

Giới hạn bucket đã đóng trong ngày hiện tại:

```bash
python main.py features-intraday --date 10/07/2026 --as-of 14:30 --symbols SSI
```

### Backfill theo khoảng ngày bao gồm cả hai đầu

```bash
python main.py features-daily \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG
```

```bash
python main.py features-intraday \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG \
  --timeframes 15m 60m
```

Range mode đọc dữ liệu nguồn đến hết ngày `to`, tính indicator một lần với phần lịch sử trước đó để warm-up, sau đó chỉ upsert các row feature nằm trong khoảng yêu cầu.

### Toàn bộ lịch sử

```bash
python main.py features-daily --mode full --symbols SSI HPG
python main.py features-intraday --mode full --symbols SSI HPG --timeframes 15m 60m
```

## Validation phạm vi

CLI trả exit code `2` khi:

- chỉ có một trong hai tham số `--from` hoặc `--to`;
- dùng `--date` chung với `--from/--to`;
- dùng `--mode full` chung với `--date` hoặc `--from/--to`;
- dùng `--as-of` với range mode;
- incremental mode không có `--date` hoặc `--from/--to`;
- khoảng ngày bị đảo hoặc ngày kết thúc nằm trong tương lai.

## Quy tắc correctness và an toàn

- Không tính feature daily từ intraday.
- 15m/60m luôn aggregate từ clean 1m trong memory và không ghi ngược vào `stock_intraday`.
- Intraday chỉ ghi bucket đã đóng.
- EMA/RSI/MACD có lịch sử trước đó để warm-up.
- Thiếu input giữ `NULL`, không ép thành 0 hoặc `False`.
- `stock_intraday.value` vẫn là giá trị ước tính `round(close * volume)`.
- Ingest, feature, signal và backtest vẫn là các pipeline tách biệt.

## Ảnh hưởng database

Migration: none.

Range và full chỉ ghi bảng `features`. Các bảng nguồn chỉ được đọc. Không tự động backfill dữ liệu nguồn.