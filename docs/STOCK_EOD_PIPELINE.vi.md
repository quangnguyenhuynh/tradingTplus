# Pipeline Stock Daily EOD

`stock-eod` là pipeline dữ liệu nguồn daily-only. Workflow độc lập chạy lúc 09:30 UTC (16:30 Asia/Ho_Chi_Minh), thứ Hai-thứ Sáu, hoặc manual.

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

Khi bỏ ngày, pipeline chọn ngày trong tuần gần nhất tính cả hôm nay theo giờ Việt Nam; fallback lịch này không chứng minh đó là phiên giao dịch. Khi bỏ symbols, scope là `symbols.status='active'`. Symbols explicit được normalize rồi giao với scope daily; mã inactive/unknown được báo trong `ignored_symbols`.

Các stage: resolve scope, nguồn SSI daily đã resolve (mặc định v3 `securities-summary`; v2 `DailyStockPrice` chỉ là fallback deprecated explicit), raw `stock_raw_daily`, clean đã validate `stock_daily`, rồi `check_daily_ingest`. Final status chỉ dùng bằng chứng daily. Compatibility key deprecated `intraday_summary` luôn là `null`.

Pipeline không gọi `IntradayOhlc`, không đọc/ghi intraday hoặc index, và không chạy feature, signal, backtest, Historical Analog hay automatic backfill.

## Completeness của run hiện tại và provenance canonical

Completeness của Stock EOD báo cả sự hiện diện canonical và các row được cập nhật kể từ lúc run bắt đầu. Row chỉ đạt current-run khi `updated_at` đủ mới và `source` khớp provider đã resolve.

`stock_daily.source` là provenance của persistence, không phải field market-data trong contract SSI. `ssi_v3` nghĩa là row canonical hiện tại được ghi thành công gần nhất từ SSI v3; `ssi_v2` nghĩa là row được ghi gần nhất qua fallback v2 deprecated explicit. `NULL` được giữ cho row lịch sử không thể xác định provider an toàn và không được hiểu là v2. Nếu response có nhiều provider record cho cùng symbol/date, pipeline giữ từng raw record nhưng không ghi clean canonical mơ hồ.
