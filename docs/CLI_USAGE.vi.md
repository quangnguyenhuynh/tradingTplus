# Sử dụng CLI

Tài liệu English đầy đủ: [CLI_USAGE.md](CLI_USAGE.md).

## Thứ tự vận hành

```text
sync-master-data
-> daily / intraday-ingest / eod / backfill
-> validation và completeness
-> feature chạy riêng
-> historical analog Phase 1 trong tương lai
```

Ingest không tự chạy feature, signal hoặc backtest.

## Command dữ liệu nguồn

```bash
python main.py sync-master-data
python main.py daily [DD/MM/YYYY] --symbols SSI HPG
python main.py intraday-ingest [DD/MM/YYYY] --symbols SSI HPG
python main.py eod [DD/MM/YYYY] --symbols SSI HPG
python main.py backfill-daily --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill-intraday --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
python main.py backfill --from DD/MM/YYYY --to DD/MM/YYYY --symbols SSI HPG
```

- `daily` đọc `DailyStockPrice`, ghi `raw_daily` và `stock_daily`.
- `intraday-ingest` đọc `IntradayOhlc` resolution 1, ghi nến nguồn clean 1m.
- `eod` chạy ingest daily, intraday rồi completeness; không tính feature.
- Backfill dùng hai đầu ngày inclusive và không tự chạy feature backfill.

## Command feature

Feature production chỉ lưu `1d`, `15m`, `60m`:

```bash
python main.py features-daily --mode incremental --date DD/MM/YYYY --symbols SSI HPG
python main.py features-intraday --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m
python main.py features --mode incremental --date DD/MM/YYYY --symbols SSI HPG --timeframes 15m 60m 1d
```

- `1d` đọc `stock_daily`.
- `15m`/`60m` aggregate từ clean 1m `stock_intraday`.
- `full` tính lại và upsert toàn scope, không delete trước.
- `incremental` dùng watermark riêng từng symbol/timeframe và warm-up.
- `replace`/`rebuild-clean` chỉ cho đúng một symbol, một timeframe và range ngày
  rõ ràng; cần RPC migration đã deploy.

`python main.py intraday` là alias feature legacy, không phải ingest SSI.

## Command fixed-rule đang đóng băng

Các group sau vẫn tồn tại trong code:

```bash
python main.py strategies list
python main.py strategies --help
python main.py signals --help
```

Chúng triển khai luồng research cũ `rule -> backtest -> approve -> signal` đã bị
thay thế. Không chạy write/approval production và không dùng metrics của chúng
làm evidence cho historical analog. Phần này chỉ ghi đúng hiện trạng executable,
không phải hướng dẫn vận hành.

## Hướng Phase 1 đã chốt

Xem [`phase1/HISTORICAL_ANALOG_SPEC.vi.md`](phase1/HISTORICAL_ANALOG_SPEC.vi.md).
Mỗi mã chỉ đối chiếu lịch sử của chính nó ở cùng checkpoint. CLI `analogs` và
các bảng đề xuất trong spec **chưa được code**; không chạy command minh họa cho
đến khi có task triển khai, migration, test và scope historical build rõ ràng.

## Kiểm tra offline

```bash
python -m compileall main.py src scripts
python main.py --help
python -m pytest -q
```

Smoke test SSI/Supabase mặc định read-only nếu chưa có exact write scope được
duyệt.
