# Pipeline Stock Daily EOD

`stock-eod` là pipeline dữ liệu nguồn daily-only. Workflow độc lập chạy lúc 09:30 UTC (16:30 Asia/Ho_Chi_Minh), thứ Hai-thứ Sáu, hoặc manual.

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

Khi bỏ ngày, pipeline chọn ngày trong tuần gần nhất tính cả hôm nay theo giờ Việt Nam; fallback lịch này không chứng minh đó là phiên giao dịch. Khi bỏ symbols, scope là `symbols.status='active'`. Symbols explicit được normalize rồi giao với scope daily; mã inactive/unknown được báo trong `ignored_symbols`.

Các stage: resolve scope, SSI `DailyStockPrice`, raw `stock_raw_daily`, clean đã validate `stock_daily`, rồi `check_daily_ingest`. Final status chỉ dùng bằng chứng daily. Compatibility key deprecated `intraday_summary` luôn là `null`.

Pipeline không gọi `IntradayOhlc`, không đọc/ghi intraday hoặc index, và không chạy feature, signal, backtest, Historical Analog hay automatic backfill.
