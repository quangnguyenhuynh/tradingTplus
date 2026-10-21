# src/providers/ssi

Hợp đồng provider và registry SSI v3. Chỉ Stock Daily và Index Daily sẵn sàng production; không có v2 hoặc fallback.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `base.py`
- `capabilities.py`
- `registry.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## Triển khai capability trong tương lai

Intraday: chỉ thêm adapter/mapping sau khi xác minh response SSI v3 1m, đơn vị, timestamp và convention đầu/cuối candle. Output phải giữ hợp đồng `stock_intraday`: symbol, market time có timezone, timeframe `1m`, OHLCV/value nullable và context giá. Giữ raw payload, reject timestamp sai, validate trước clean write. Không suy đoán alias từ v2. Chỉ bật lại sau khi kiểm tra pagination, scope, idempotency, phiên giao dịch và không partial-write.

Master: triển khai adapter/mapping riêng trong `providers/ssi/adapters` và service ở `ingest/master`; giữ status do operator điều khiển, không suy luận danh sách mã từ lịch sử giá, không sync master ngầm trong ingest.

Streaming: cần protocol và cơ chế xác thực được kiểm chứng riêng ở `ingest/streaming`; decoder payload lịch sử không chứng minh tính tương thích v3. Chỉ khôi phục lịch sau khi capability được kiểm chứng.

SSI v4 tương lai: thêm client, adapter theo DataSourceAdapter/AdapterResult, mapping JSON có version và entry registry theo dataset. Adapter cung cấp source của raw; chỉ đánh dấu ready sau fixture/semantic tests. Không đổi logic ingest và không fallback. Task này không triển khai v4.

## Preview intraday SSI v3 nhiều trang (chỉ đọc)

Route `stock-intraday`/native `intraday-ohlc` của REST inspector nay dùng adapter preview chung và tải mọi trang từ trang bắt đầu đến kết thúc tường minh hoặc lỗi/giới hạn. `--limit` chỉ giới hạn in; `--full-json` bao gồm mọi trang raw đã nhận và clean candidate. `--max-pages` mặc định 100 (1–1000); chạm giới hạn, trang lặp, total không khớp hay lỗi request trả FAILED/exit 1 và giữ bằng chứng đã nhận. Không đổi các route daily/index/catalog một-trang của inspector.

Không có credential SSI trong môi trường kiểm tra: live NOT_RUN. Ngữ nghĩa v3 vẫn PROVISIONAL, completeness luôn UNVERIFIED. Chỉ timestamp đầy đủ có timezone được chuyển UTC; timestamp naive/chỉ giờ/chỉ ngày bị từ chối, không ghép ngày request. Giá/volume chưa được chứng nhận đơn vị; value ước tính dùng round(close * volume), field source value giữ raw. Production CLI và schedule intraday vẫn tắt; preview không đọc/ghi Supabase.

Xem [runbook và checklist](../../../docs/STOCK_INTRADAY_PIPELINE.vi.md) để biết mapping từng field, paging, validation/session/gap, giới hạn nguồn và cách promotion riêng.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```
