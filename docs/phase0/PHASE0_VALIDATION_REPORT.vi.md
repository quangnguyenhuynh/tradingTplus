# Báo cáo kiểm chứng Phase 0

**Quyết định: BLOCKED**  
**Baseline repository:** `9af7485952833917669312ae9b15961f583729b6` (PR #117)
**Ngày kiểm chứng offline:** 02/08/2026  
**Môi trường:** môi trường test tương thích Python 3.11, fixture deterministic; không có credential SSI/Supabase/GitHub hoặc project Supabase đã link.

Phase 0 chưa hoàn thành. Pagination offline, parity feature lịch sử dài và contract atomic replace đã có evidence; shared SSI reader nay có pagination bounded/cycle-safe. Tuy nhiên không thể thu thập evidence live/schema production. Không query hay thay đổi production.

## Evidence pagination offline

Mọi reader PostgREST của feature và completeness được test với ordering ổn định, request 1.000 row, server cap giả lập 500 hoặc 400, trang cuối ngắn và trang rỗng kết thúc. Offset tăng theo số row thực trả. Test giữ filter symbol/timeframe/time/date, từ chối page size không dương, kiểm tra limit chính xác và phát hiện trang lặp. Client SSI dùng page index tiếp tục sau trang ngắn do cap, validate `totalRecord`, hash row không phụ thuộc thứ tự, từ chối cycle A→A/A→B→A/A→B→C→A và shuffled-row, đồng thời dừng page thay đổi vô tận tại safety bound 10.000 page mà không trả partial data.

Fixture 251 phiên có bảy candle mỗi ngày quan sát. Server cap 1.747 row chia ngày cũ nhất được chọn (phiên thứ 250) qua hai trang descending. Reader trả đủ bảy candle của ngày đó, đúng 250 ngày, không có candle của ngày cũ thứ 251 và không trùng candle tại boundary.

Fixture completeness đọc 1.205 symbol/row qua cap 400 (bốn trang dữ liệu cộng một trang rỗng) mà không bị cắt.

## Evidence parity lịch sử dài

So sánh sau serialization production. Mọi cột feature persisted được so sánh; symbol, timeframe, time, integer, boolean và NULL phải bằng tuyệt đối. Float dùng tolerance tuyệt đối `1e-6` hoặc tương đối `1e-9`, phù hợp serialization sáu chữ số thập phân. Chỉ loại audit field `last_updated_at`.

| Timeframe | Nguồn full | Nguồn bounded | Target | Chênh lệch tuyệt đối lớn nhất | Chênh lệch tương đối lớn nhất |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | 1.501 row ngày trong tuần (>5 năm) | 1.306 row (window 5 năm production) | ngày cuối | 0 cho mọi cột float | 0 cho mọi cột float |
| `15m`, 200 phiên | 15.060 row `1m` / 251 ngày | 12.000 row | ngày cuối | 0 | 0 |
| `15m`, 250 phiên | 15.060 row `1m` / 251 ngày | 15.000 row | ngày cuối | 0 | 0 |
| `60m`, 200 phiên | 15.060 row `1m` / 251 ngày | 12.000 row | ngày cuối | 0 | 0 |
| `60m`, 250 phiên | 15.060 row `1m` / 251 ngày | 15.000 row | ngày cuối | 0 | 0 |

Fixture có OHLCV/value deterministic nhưng không hằng, có phiên sáng, chiều và nghỉ trưa. Test aggregation riêng chứng minh không gộp qua nghỉ trưa hay ngày Việt Nam. Với request 1.000 row, full intraday cần 16 trang dữ liệu, scope 200 phiên cần 12 và default 250 phiên cần 15; mode bounded không mặc định đọc toàn lịch sử. Daily bounded giảm 195 row, dù cả full và bounded đều cần hai trang dữ liệu trong fixture này.

Evidence ủng hộ giữ default 250 phiên quan sát. Fixture 200 phiên cũng khớp target deterministic này, nhưng không phải default production và một test không chứng minh 200 luôn đủ cho mọi chuỗi thật.

## Atomic replace và migration

Migration vẫn chỉ cho service role, `SECURITY DEFINER`, `search_path` rỗng, validate đúng symbol/timeframe/range nửa mở, từ chối payload rỗng/trùng, delete/insert trong một transaction và bảo vệ rollback. GitHub Actions bình thường chạy toàn suite với PostgreSQL 16 và `TEST_DATABASE_URL`; integration test không được cấu hình skip.

Trạng thái production là **UNKNOWN**. Không có project Supabase link hoặc credential nên không query migration pending, privilege function, index bắt buộc hay metadata production của `raw_intraday.payload`. Không apply migration được cho phép nào trong task này. Không đổi row production. Payload lịch sử chủ ý không backfill; ingest mới giữ object candle semantic đầy đủ trong JSONB nullable.

## Ma trận contract/evidence SSI

Runtime này không truy cập được file PDF đính kèm. Theo override của task, các contract fact đã được review bên ngoài dưới đây mang nhãn `DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW`; báo cáo không tuyên bố Codex tự mở PDF. Behavior live vẫn tách riêng thành `OBSERVED`, `INFERRED_BY_CODE` hoặc `UNKNOWN`.

| Hạng mục trọng yếu | Phân loại | Evidence / blocker |
| --- | --- | --- |
| Endpoint `DailyStockPrice` | `DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW` | `/api/v2/Market/DailyStockPrice`, nguồn daily canonical; field live chưa quan sát. |
| `DailyOhlc` để so sánh | `DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW` | Có tài liệu và chỉ dùng đối chiếu; chưa quan sát live. |
| `IntradayOhlc` resolution `1` | `DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW` | Resolution `1` có tài liệu; semantic volume/value live vẫn unknown. |
| Tham số pagination SSI | `DOCUMENTED_FROM_EXTERNAL_PDF_REVIEW` | Có `pageIndex`, `pageSize`, `totalRecord`; độ tin cậy live chưa được chứng minh. Cycle safety là `INFERRED_BY_CODE` và test offline. |
| Equality/hash `raw_daily.payload` | `UNKNOWN` | Thiếu raw row production và source object live. |
| Giữ nested/unknown field trong `raw_intraday.payload` | `INFERRED_BY_CODE` | Code/test mapper; chưa verify migration/sample production. |
| Ý nghĩa timestamp intraday | `INFERRED_BY_CODE` | Có parse giờ Việt Nam/lưu UTC; chưa có evidence source. |
| Ý nghĩa volume intraday | `UNKNOWN` | Thiếu PDF/live bắt buộc. |
| Value intraday | `INFERRED_BY_CODE` | Value clean là ước lượng `round(close * volume)`, không gọi là turnover SSI chính xác. |
| Response cuối tuần | `UNKNOWN` | Thiếu authentication/live request. |
| Response ngày lễ weekday chính thức | `UNKNOWN` | Thiếu live request và calendar authoritative. |

Không contract item nào được phân loại `OBSERVED` trong run này vì thiếu live SSI access.

## Đối chiếu live

Không chọn hoặc query sample live: chọn đúng symbol thanh khoản/cạn thanh khoản có dữ liệu, bucket đã đóng, ngày feature và hash production cần quyền read-only database; so sánh source cần authentication SSI. Vì vậy daily raw-to-clean, intraday raw-to-clean, tái tạo clean-to-feature độc lập, hành vi cuối tuần và ngày lễ chính thức đều blocked. Báo cáo không dựng ngày hay payload giả.

## Gate completeness

Test offline cover ngày hoàn chỉnh về cấu trúc, thiếu một interval, duplicate, thiếu phiên chiều, gap dài, bucket trống rời rạc kiểu thanh khoản thấp và pagination cap trên 1.000 row. Report có count, first/last time, duplicate, interval/phút thiếu, loại gap và reason, không dùng universal 226 candle. Summary public `OK/PARTIAL/FAILED` giữ tương thích.

Repository chưa có nguồn calendar/status sàn authoritative được duyệt. Không thể phân biệt an toàn ngày lễ chính thức trong tuần với ngày giao dịch không có data hoặc lỗi source/auth chỉ từ row lưu trữ. Task không phát minh holiday list. Đây là blocker Phase 0.

## Ảnh hưởng database và backfill

Không tạo migration mới, không ghi production, ingest, replace, backfill, dựng payload hay rebuild feature. Không đổi formula feature nên không cần rebuild. `schema.sql` cộng migrations theo thứ tự là canonical; snapshot lịch sử dư thừa `docs_db_schema.md` đã bị xóa.

## Blocker còn lại

1. Không có credential/response SSI live.
2. Không có project Supabase production link và credential read-only.
3. Không biết và chưa verify trạng thái hai migration được phép trên production.
4. Chưa duyệt nguồn calendar/status sàn authoritative có version.
5. Không có GitHub authentication nên không xem được CI và không comment/đóng Issue #110.

Issue #110 và Phase 0 phải tiếp tục mở.
