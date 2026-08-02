# Tích hợp SSI

Client cho SSI FastConnect Data REST và classic ASP.NET SignalR streaming.

## Tài liệu

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)
- Kiểm tra REST: [`../../scripts/ssi_api_inspector/`](../../scripts/ssi_api_inspector/README.vi.md)
- Kiểm tra streaming: [`../../scripts/ssi_streaming_inspector/`](../../scripts/ssi_streaming_inspector/README.vi.md)

## File

- `api.py`: authentication, REST request, paging, lấy dữ liệu từ response và helper endpoint.
- `streaming.py`: SignalR negotiate/subscribe và xử lý message có giới hạn.
- `__init__.py`: export package.

## Hợp đồng REST

Project dùng các endpoint SSI có tài liệu như `AccessToken`, `Securities`, `SecuritiesDetails`, `IndexComponents`, `IndexList`, `DailyOhlc`, `IntradayOhlc`, `DailyIndex`, `DailyStockPrice` ở nơi đã implement.

- `DailyStockPrice` là nguồn daily chuẩn.
- `DailyOhlc` chỉ để đối chiếu.
- `IntradayOhlc` dùng resolution 1 cho dữ liệu intraday lưu DB.
- Foreign trading derive từ field daily-stock-price.
- Không tự tạo public REST endpoint orderbook hoặc foreign trading.

## An toàn và lỗi

- Lấy credential từ cấu hình môi trường.
- Không log consumer secret, bearer token hoặc authorization header.
- Retry authentication theo chính sách có giới hạn.
- Xử lý rõ response rỗng, sai hoặc đổi envelope.
- Không tạo dòng giả khi SSI không trả dữ liệu.
- Pagination dùng hash không phụ thuộc thứ tự cho mọi page, giữ toàn bộ hash đã
  thấy và raise `SSIPaginationError` khi page lặp hoặc cycle dài bất kỳ. Page
  ngắn không phải EOF. Chỉ `totalRecord` chính xác đáng tin, page rỗng hoặc
  caller limit đạt chính xác mới kết thúc bình thường.
- `SSI_MAX_PAGES_PER_REQUEST` là safety bound mặc định có tên (10.000 page).
  Caller có thể giảm theo request; chạm bound là lỗi, không trả partial data.
  Total sai/thay đổi hoặc số row vượt total đã công bố đều là lỗi.
- Tool streaming phải có symbol/channel rõ ràng, timeout/số message giới hạn và mặc định read-only.

## Ranh giới evidence

Review bên ngoài của SSI FastConnect Data Specs v2.2 xác nhận
`DailyStockPrice` tại `/api/v2/Market/DailyStockPrice`, `DailyOhlc` chỉ dùng đối
chiếu và `IntradayOhlc` hỗ trợ resolution `1`. Repository ghi nhận bằng
`DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW`; không tuyên bố runtime agent đã mở file
đính kèm. Tài liệu không chứng minh pagination live luôn đáng tin, ngữ nghĩa
volume intraday dùng chung cho mọi response hoặc intraday turnover chính xác.
Các mục đó vẫn cần validation live read-only riêng.

Dùng inspector read-only để kiểm tra payload lạ trước khi sửa mapping ingest.
