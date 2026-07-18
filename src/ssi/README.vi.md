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
- Tool streaming phải có symbol/channel rõ ràng, timeout/số message giới hạn và mặc định read-only.

Dùng inspector read-only để kiểm tra payload lạ trước khi sửa mapping ingest.
