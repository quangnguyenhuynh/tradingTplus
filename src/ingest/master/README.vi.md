# src/ingest/master

NOT_IMPLEMENTED: đồng bộ master. Giữ model thuần và hợp đồng status do operator điều khiển; không đọc/ghi DB trong entrypoint bị chặn.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `index_master.py`
- `init_symbols.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Triển khai capability trong tương lai

Intraday: chỉ thêm adapter/mapping sau khi xác minh response SSI v3 1m, đơn vị, timestamp và convention đầu/cuối candle. Output phải giữ hợp đồng `stock_intraday`: symbol, market time có timezone, timeframe `1m`, OHLCV/value nullable và context giá. Giữ raw payload, reject timestamp sai, validate trước clean write. Không suy đoán alias từ v2. Chỉ bật lại sau khi kiểm tra pagination, scope, idempotency, phiên giao dịch và không partial-write.

Master: triển khai adapter/mapping riêng trong `providers/ssi/adapters` và service ở `ingest/master`; giữ status do operator điều khiển, không suy luận danh sách mã từ lịch sử giá, không sync master ngầm trong ingest.

Streaming: cần protocol và cơ chế xác thực được kiểm chứng riêng ở `ingest/streaming`; decoder payload lịch sử không chứng minh tính tương thích v3. Chỉ khôi phục lịch sau khi capability được kiểm chứng.

SSI v4 tương lai: thêm client, adapter theo DataSourceAdapter/AdapterResult, mapping JSON có version và entry registry theo dataset. Adapter cung cấp source của raw; chỉ đánh dấu ready sau fixture/semantic tests. Không đổi logic ingest và không fallback. Task này không triển khai v4.
