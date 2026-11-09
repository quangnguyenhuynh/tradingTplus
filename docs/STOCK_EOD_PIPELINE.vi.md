# Trạng thái hiện tại / Current capability status

## Numeric daily chính xác — 04/11/2026

Daily mapping/contract 3.0.0: tiền/giá/level/phần trăm dùng Decimal, quantity
rời rạc dùng integer chính xác. Stock policy 1.1.0 giữ phần lẻ tiền với warning
FRACTIONAL_MONETARY_VALUE/PARTIAL; Index giữ pipeline riêng, reject numeric sai.
Cần owner apply **migration mới** `20261104_daily_numeric_precision.sql`; không
sửa migration V1 cũ, không tự rewrite/backfill/features.
Diagnostic chỉ đọc: `python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(đổi dataset index_daily/identifiers VNINDEX cho Index).
[Bảng field, transport, audit, SQL/deploy/rollback và lệnh owner](DAILY_NUMERIC_PRECISION.vi.md).
Hướng dẫn integer-money/float của daily trước đây được policy này thay thế; các ghi nhận test lịch sử vẫn là evidence tại thời điểm chạy.


## Stock Daily Data Quality V1 — 03/11/2026

SSI v3 Stock Daily dùng VALID/PARTIAL/REJECTED, quarantine optional lỗi thành NULL,
giữ RAW bất biến và log hiện tại/lịch sử. Cần owner apply migration
`20261103_stock_daily_quality_v1.sql` trước writer mới; status lịch sử giữ NULL.
Diagnostic chỉ đọc mới: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Giữ tên `stock-eod`/`stock-eod-backfill`; không tự backfill/features.
[Policy, triển khai, SQL kiểm tra và rerun đúng scope](STOCK_DAILY_QUALITY_V1.vi.md).


Stock Daily EOD vẫn ACTIVE qua SSI v3; chỉ daily ingest và daily completeness.

[CLI hiện tại](CLI_USAGE.md) · [Current state](CURRENT_STATE.md)

## Historical operational record

Các hướng dẫn vận hành cũ bên dưới được giữ làm lịch sử; phần mâu thuẫn với trạng thái trên đã được thay thế. Không chạy lại hướng dẫn v2.

> Historical operational note: SSI v2 REST and legacy SignalR are RETIRED. Intraday/master/streaming ingestion and combined backfill/refill are NOT_IMPLEMENTED. Any older operational instructions below are superseded by [current status](CURRENT_STATE.md). Historical data, formulas and evidence remain unchanged.

# Pipeline Stock Daily EOD

`stock-eod` là pipeline dữ liệu nguồn daily-only. Workflow mới chạy lúc **10:07 UTC (17:07 giờ Việt Nam), thứ Hai–thứ Sáu**, hoặc chạy thủ công. File hiện hành: `.github/workflows/stock-eod-scheduled.yml`.

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

Khi bỏ ngày, pipeline chọn ngày trong tuần gần nhất tính cả hôm nay theo giờ Việt Nam; fallback lịch này không chứng minh đó là phiên giao dịch. Khi bỏ symbols, scope là `symbols.status='active'`. Symbols explicit được normalize rồi giao với scope daily; mã inactive/unknown được báo trong `ignored_symbols`.

Workflow theo lịch truyền tường minh ngày thứ Hai–thứ Sáu đang chạy tại Việt Nam dưới dạng `DD/MM/YYYY`; job dùng **mốc 17:07 thứ Hai–thứ Sáu gần nhất đã qua** theo giờ Việt Nam, kể cả chạy sau nửa đêm hoặc cuối tuần. Log ghi mốc và ngày mục tiêu. Nếu trễ qua mốc lịch kế tiếp, job có thể chọn mốc mới; phiên cũ cần được chạy tay với ngày tường minh. Chạy thủ công có ngày thì giữ đúng ngày yêu cầu; để trống ngày thì gọi CLI không kèm ngày và giữ nguyên hành vi mặc định cũ. GitHub Actions có thể bắt đầu trễ; slot lỡ cần chạy tay với ngày tường minh.

Các stage: resolve scope, nguồn SSI v3 daily đã resolve (`securitiesSummary`; v2 đã retired và không khả dụng), raw `stock_raw_daily`, clean đã validate `stock_daily`, rồi `check_daily_ingest`. Final status chỉ dùng bằng chứng daily. Compatibility key deprecated `intraday_summary` luôn là `null`.

Pipeline không gọi `IntradayOhlc`, không đọc/ghi intraday hoặc index, và không chạy feature, signal, backtest, Historical Analog hay automatic backfill.

## Completeness của run hiện tại và provenance canonical

Completeness của Stock EOD báo cả sự hiện diện canonical và các row được cập nhật kể từ lúc run bắt đầu. Row chỉ đạt current-run khi `updated_at` đủ mới và `source` khớp provider đã resolve.

`stock_daily.source` là provenance của persistence, không phải field market-data trong contract SSI. `ssi_v3` nghĩa là row canonical hiện tại được ghi thành công gần nhất từ SSI v3; `ssi_v2` là provenance lịch sử; provider v2 hiện đã retired và không khả dụng. `NULL` được giữ cho row lịch sử không thể xác định provider an toàn và không được hiểu là v2. Nếu response có nhiều provider record cho cùng symbol/date, pipeline giữ từng raw record nhưng không ghi clean canonical mơ hồ.
