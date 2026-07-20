# Test feature

Test việc tính feature deterministic và ghi dữ liệu đúng theo timeframe.

Phạm vi gồm đọc nguồn 1m, aggregate 5m/15m/60m, feature 1d từ `stock_daily`, warm-up history, pagination, lọc target date, breakout không look-ahead, reset theo phiên và hợp đồng một bảng `features`.

```bash
python -m pytest -q tests/features
```
