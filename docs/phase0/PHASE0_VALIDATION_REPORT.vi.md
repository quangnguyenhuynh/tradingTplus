# Báo cáo kiểm chứng Phase 0

**Quyết định: BLOCKED**  
**Baseline repository:** `f80244bb350d3876762532241e372e0f0d2d1f71` (PR #116)  
**Ngày kiểm chứng offline:** 02/08/2026  
**Môi trường:** môi trường test tương thích Python 3.11, fixture deterministic; không có credential SSI/Supabase/GitHub hoặc project Supabase đã link.

Phase 0 chưa hoàn thành. Pagination offline, parity feature lịch sử dài và contract atomic replace trong repository đã có evidence, nhưng thiếu PDF SSI bắt buộc và không thể thu thập evidence live/schema production. Không query hay thay đổi production.

## Evidence pagination offline

Mọi reader PostgREST của feature và completeness được test với ordering ổn định, request 1.000 row, server cap giả lập 500 hoặc 400, trang cuối ngắn và trang rỗng kết thúc. Offset tăng theo số row thực trả. Test giữ filter symbol/timeframe/time/date, từ chối page size không dương, kiểm tra limit chính xác và phát hiện trang lặp. Client SSI dùng page index cũng tiếp tục sau trang ngắn do cap, tôn trọng `totalRecord` và từ chối trang lặp.

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

Không tìm thấy `SSI_FastConnectData_Specs_v2.2.pdf` trong repository hoặc đường dẫn attachment truy cập được. Vì vậy không phân loại hành vi nào là SSI documented chỉ dựa vào tài liệu repository.

| Hạng mục trọng yếu | Phân loại | Evidence / blocker |
| --- | --- | --- |
| Endpoint/field `DailyStockPrice` | `INFERRED_BY_CODE` | Client/mapper dùng làm canonical; thiếu PDF và live response. |
| `DailyOHLC` để so sánh | `INFERRED_BY_CODE` | Inspector/client chỉ dùng so sánh; chưa quan sát live. |
| Field/unit `IntradayOHLC` resolution `1` | `INFERRED_BY_CODE` | Chỉ có contract code/mapper. |
| Pagination/cap SSI | `INFERRED_BY_CODE` | Hành vi phòng vệ và fixture offline. |
| Equality/hash `raw_daily.payload` | `UNKNOWN` | Thiếu raw row production và source object live. |
| Giữ nested/unknown field trong `raw_intraday.payload` | `INFERRED_BY_CODE` | Code/test mapper; chưa verify migration/sample production. |
| Ý nghĩa timestamp intraday | `INFERRED_BY_CODE` | Có parse giờ Việt Nam/lưu UTC; chưa có evidence source. |
| Ý nghĩa volume intraday | `UNKNOWN` | Thiếu PDF/live bắt buộc. |
| Value intraday | `INFERRED_BY_CODE` | Value clean là ước lượng `round(close * volume)`, không gọi là turnover SSI chính xác. |
| Response cuối tuần | `UNKNOWN` | Thiếu authentication/live request. |
| Response ngày lễ weekday chính thức | `UNKNOWN` | Thiếu live request và calendar authoritative. |

Run này không có `DOCUMENTED_AND_OBSERVED`, `DOCUMENTED_NOT_OBSERVED` hoặc `OBSERVED_NOT_DOCUMENTED` vì thiếu cả tài liệu cung cấp và live access.

## Đối chiếu live

Không chọn hoặc query sample live: chọn đúng symbol thanh khoản/cạn thanh khoản có dữ liệu, bucket đã đóng, ngày feature và hash production cần quyền read-only database; so sánh source cần authentication SSI. Vì vậy daily raw-to-clean, intraday raw-to-clean, tái tạo clean-to-feature độc lập, hành vi cuối tuần và ngày lễ chính thức đều blocked. Báo cáo không dựng ngày hay payload giả.

## Gate completeness

Test offline cover ngày hoàn chỉnh về cấu trúc, thiếu một interval, duplicate, thiếu phiên chiều, gap dài, bucket trống rời rạc kiểu thanh khoản thấp và pagination cap trên 1.000 row. Report có count, first/last time, duplicate, interval/phút thiếu, loại gap và reason, không dùng universal 226 candle. Summary public `OK/PARTIAL/FAILED` giữ tương thích.

Repository chưa có nguồn calendar/status sàn authoritative được duyệt. Không thể phân biệt an toàn ngày lễ chính thức trong tuần với ngày giao dịch không có data hoặc lỗi source/auth chỉ từ row lưu trữ. Task không phát minh holiday list. Đây là blocker Phase 0.

## Ảnh hưởng database và backfill

Không tạo migration mới, không ghi production, ingest, replace, backfill, dựng payload hay rebuild feature. Không đổi formula feature nên không cần rebuild. `schema.sql` cộng migrations theo thứ tự là canonical; snapshot lịch sử dư thừa `docs_db_schema.md` đã bị xóa.

## Blocker còn lại

1. Không có PDF SSI do user cung cấp.
2. Không có credential/response SSI live.
3. Không có project Supabase production link và credential read-only.
4. Không biết và chưa verify trạng thái hai migration được phép trên production.
5. Chưa duyệt nguồn calendar/status sàn authoritative có version.
6. Không có GitHub authentication nên không xem được CI và không comment/đóng Issue #110.

Issue #110 và Phase 0 phải tiếp tục mở.
