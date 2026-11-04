# src/contracts

## Numeric daily chính xác — 04/11/2026

Daily mapping/contract 3.0.0: tiền/giá/level/phần trăm dùng Decimal, quantity
rời rạc dùng integer chính xác. Stock policy 1.1.0 giữ phần lẻ tiền với warning
FRACTIONAL_MONETARY_VALUE/PARTIAL; Index giữ pipeline riêng, reject numeric sai.
Cần owner apply **migration mới** `20261104_daily_numeric_precision.sql`; không
sửa migration V1 cũ, không tự rewrite/backfill/features.
Diagnostic chỉ đọc: `python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(đổi dataset index_daily/identifiers VNINDEX cho Index).
[Bảng field, transport, audit, SQL/deploy/rollback và lệnh owner](../../docs/DAILY_NUMERIC_PRECISION.vi.md).
Hướng dẫn integer-money/float của daily trước đây được policy này thay thế; các ghi nhận test lịch sử vẫn là evidence tại thời điểm chạy.


Hợp đồng canonical, engine mapping, transform và từ điển source tách biệt; engine không chứa chi tiết endpoint.

Không thay đổi schema, công thức, profile hoặc provenance lịch sử. Không cần migration hay backfill do di chuyển code.

Các module:

- `derived.py`
- `engine.py`
- `registry.py`
- `transforms.py`

Xem README tại root và docs/CURRENT_STATE.md để biết trạng thái capability và điều kiện triển khai adapter mới.

## SSI v3 intraday — field nguồn và nullable value

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest/schedule production vẫn tắt; preview không đọc/ghi DB.

[Mapping, quy tắc và guard persistence](../../docs/STOCK_INTRADAY_PIPELINE.vi.md)

## Mapping catalog chứng khoán — 27/10/2026

symbol_list SSI v3 version 1.1.0-preview map symbolNameVi→stock_name, board→market/exchange, stockType→security_type. Optional thiếu giữ NULL, type lạ giữ text nguồn. Contract daily/intraday/index không đổi. PASS chỉ kiểm tra row mapping, không chứng minh đủ board/universe hoặc ghi DB. [Bằng chứng và provenance fixture](../../docs/SSI_V3_MASTER_EVIDENCE.vi.md).
