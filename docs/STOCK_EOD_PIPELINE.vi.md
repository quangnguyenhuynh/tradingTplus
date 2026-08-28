# Pipeline Stock EOD

## Mục đích và lịch chạy

`stock-eod` là orchestrator dữ liệu nguồn **cổ phiếu** cuối ngày. GitHub Actions chạy `.github/workflows/stock-eod.yml` lúc 09:30 UTC (16:30 Asia/Ho_Chi_Minh) từ thứ Hai đến thứ Sáu và hỗ trợ chạy manual. Workflow này độc lập với `.github/workflows/index-eod.yml`.

## Chạy manual

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

Nếu bỏ ngày, pipeline chọn ngày trong tuần gần nhất không sau ngày hiện tại theo giờ Việt Nam. Đây chỉ là fallback lập lịch, không khẳng định đó là ngày giao dịch; completeness sẽ phản ánh response rỗng hoặc thiếu.

## Scope symbol active

Pipeline đọc các dòng `symbols.status = 'active'`. Nếu bỏ `--symbols`, toàn bộ symbol active được dùng. Danh sách explicit được strip, uppercase, loại trùng theo lần xuất hiện đầu tiên, rồi giao với tập active. Symbol inactive/không tồn tại được báo trong `ignored_symbols` và không bao giờ được ingest. Cùng một list đã resolve được truyền nguyên vẹn qua mọi stage.

## Thứ tự stage và hợp đồng dữ liệu

1. Stock daily ingest: bằng chứng payload SSI `DailyStockPrice` vào `raw_daily`, sau đó row chuẩn hóa vào `stock_daily`.
2. Stock intraday ingest: bằng chứng payload SSI `IntradayOhlc` vào `raw_intraday`, sau đó candle 1 phút canonical vào `stock_intraday`.
3. Stock completeness: kiểm tra chỉ đọc theo scope active và ngày giao dịch.
4. Tổng hợp trạng thái cuối chỉ từ các stage stock.

`SUCCESS` trong mô tả vận hành tương ứng status summary `OK`: cả hai dataset stock có dữ liệu và không stage nào fail. `PARTIAL` nghĩa là completeness báo coverage stock thiếu/chưa đủ nhưng chưa fail toàn bộ. `FAILED` nghĩa là stage stock fail, completeness fail, hoặc count daily/intraday bắt buộc bằng 0.

## Các phần tuyệt đối không thuộc Stock EOD

Stock EOD không gọi `DailyIndex`, không đọc `index_master`, không ghi `index_raw_daily`/`index_daily`, và không chạy index completeness. Index do `index-eod` độc lập xử lý. Stock EOD không tính feature, signal, backtest hoặc Historical Analog. “EOD” trong Historical Analog vẫn là tên checkpoint và không bị đổi bởi việc chuẩn hóa interface pipeline này.
