# Trading T+ — SSI v3

Nền tảng dữ liệu và nghiên cứu historical analog cùng mã cho chứng khoán Việt Nam, kỳ nắm giữ T+3 đến T+5 phiên. Phase 0: `COMPLETE_WITH_NOTES`.

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

Xem [English](README.md), [CLI](docs/CLI_USAGE.vi.md), [trạng thái](docs/CURRENT_STATE.md), [bản đồ file](docs/RESTRUCTURE_MAPPING.json), [quy ước dữ liệu](docs/DATA_CONVENTIONS.vi.md) và [đặc tả Analog](docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).
