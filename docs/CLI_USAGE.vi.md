# Hướng dẫn CLI — SSI v3

Chạy `python main.py COMMAND --help` tại root để xem tham số đầy đủ. Exit 0: OK/PARTIAL ở luồng được hỗ trợ; exit 1: FAILED hoặc NOT_IMPLEMENTED; exit 2: tham số/source không hợp lệ.

Chỉ SSI v3 REST còn được triển khai: Stock Daily dùng `securitiesSummary`; Index Daily dùng `indexSummary`. SSI v2 REST và kết nối SignalR cũ đã được gỡ bỏ. Không có fallback v2.

Stock Intraday ingest, đồng bộ master data và Streaming/Orderbook: `NOT_IMPLEMENTED`. Các lệnh vẫn parse tham số nhưng trả exit 1, JSON `status=FAILED`, `error_type=NOT_IMPLEMENTED` trước mọi truy cập SSI/Supabase. `backfill` và `refill` cũng bị chặn trước khi chạy phần daily; `backfill-daily` vẫn hoạt động riêng.

Dữ liệu clean 1m lịch sử vẫn dùng được cho `features-intraday`. Stock/Foreign/Index features, Screener V1/V2 và Historical Analog vẫn chạy độc lập; công thức, profile và hợp đồng DB được giữ nguyên. Không có thay đổi schema, migration, dữ liệu production hoặc yêu cầu backfill.

```bash
python main.py --help
python main.py stock-eod --help
python main.py index-preview --help
python main.py features-intraday --help
```

Biến môi trường SSI hiện tại: `SSI_API_KEY`, `SSI_API_SECRET`. Cấu hình Supabase giữ nguyên theo `.env.example`; không lưu credential vào Git.

Code được tách thành `src/cli`, `providers/ssi`, `contracts`, `ingest`, `quality`, `features/{stock,foreign,index}`, `research/{screener,analogs}`. Các lịch Stock/Index EOD được giữ nguyên; lịch intraday đã tắt. Chỉ bật lại sau khi adapter v3 được kiểm chứng trong domain tương ứng.


Danh sách lệnh và ví dụ đầy đủ: [CLI English](CLI_USAGE.md). Các hướng dẫn foreign/analog và công thức không thay đổi.
