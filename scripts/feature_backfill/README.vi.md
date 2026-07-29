# Backfill Feature Theo Khoảng Ngày

CLI này tính lại feature trong một khoảng ngày bao gồm cả hai đầu, không ingest lại dữ liệu nguồn SSI.

Feature production vẫn chỉ lưu:

- daily: `1d`
- intraday: `15m`, `60m`

Nến clean `stock_intraday` 1m vẫn là nguồn chuẩn để aggregate intraday. CLI không ghi feature `1m` hoặc `5m`.

## Backfill daily

```bash
python scripts/feature_backfill/run.py daily \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG
```

Runner đọc `stock_daily` tới ngày kết thúc, tính indicator một lần với toàn bộ lịch sử trước đó để warm-up, sau đó chỉ upsert các dòng feature `1d` nằm trong khoảng yêu cầu.

## Backfill intraday

```bash
python scripts/feature_backfill/run.py intraday \
  --from 01/07/2026 \
  --to 29/07/2026 \
  --symbols SSI HPG \
  --timeframes 15m 60m
```

Runner đọc lịch sử clean 1m tới ngày kết thúc, aggregate 15m/60m trong memory, tính indicator một lần với dữ liệu trước khoảng làm warm-up, sau đó chỉ upsert các bucket đã đóng nằm trong khoảng yêu cầu.

## Khác nhau với full và incremental

- `incremental`: chỉ ghi một ngày target.
- range backfill: ghi khoảng ngày `from`/`to`, bao gồm hai đầu.
- `full`: ghi lại toàn bộ lịch sử feature đang có trong bảng nguồn.

## An toàn và giới hạn

- Command chỉ ghi vào bảng `features`.
- Không ingest raw hoặc clean data.
- Không tự chạy signal hoặc backtest.
- Khoảng ngày đảo ngược và ngày kết thúc trong tương lai bị từ chối.
- Dòng hiện có được upsert theo `(symbol, timeframe, time)`.
- Nên chạy thử với ít mã và khoảng ngắn trước khi mở rộng.

## Ảnh hưởng database

Migration: none.

Các bảng dữ liệu nguồn chỉ được đọc. Không cần backfill lại source data.
