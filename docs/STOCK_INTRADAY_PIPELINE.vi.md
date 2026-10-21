# SSI v3 Stock Intraday 1m — preview chỉ đọc

[English](STOCK_INTRADAY_PIPELINE.md) · [CLI](CLI_USAGE.vi.md) · [Báo cáo bằng chứng](SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md)

## Trạng thái và bằng chứng

**READ-ONLY — gọi SSI API, không đọc/ghi DB. Ingest production vẫn NOT_IMPLEMENTED.** Đã triển khai và kiểm tra offline preview; ngữ nghĩa nguồn SSI vẫn **PROVISIONAL / PARTIAL**. Xác minh live **NOT_RUN** vì chưa cấu hình credential SSI. Repository chưa có response intraday v3 được capture thực tế. Alias/envelope hiện có và test protocol tổng hợp không phải bằng chứng live.

Registry vẫn chỉ preview, không có factory production. `intraday-ingest`, `stock-intraday`, `backfill-intraday`, `backfill` kết hợp và `refill` vẫn dừng trước truy cập service. Workflow intraday chỉ còn diagnostic thủ công báo chưa triển khai, không có schedule. Clean 1m lịch sử vẫn dùng được cho feature chạy tường minh; preview không tính feature.

## Chạy preview

Dùng venv Python 3.11 đã cài `requirements.txt`. Cấu hình `SSI_API_KEY`, `SSI_API_SECRET` tại local; không cần credential Supabase. Help/list không cần credential hay mạng. Chạy tại root repository. Ngày nhận YYYY-MM-DD hoặc DD/MM/YYYY. Các lệnh chỉ được kiểm tra offline; ví dụ mã thanh khoản SSI ngày hoàn tất 2026-10-19 là phạm vi điều tra minh họa, không khẳng định đã xem response ngày đó.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

`--show-mapping` in quy tắc dictionary và mức bằng chứng provisional. `--full-json` cung cấp mọi envelope raw, candle, candidate clean theo đúng vị trí và diagnostic từng hàng (vẫn che credential). Chế độ thường chỉ in mẫu; `--limit` chỉ giới hạn hiển thị. Lỗi ngoài mẫu vẫn được in. Raw giữ thứ tự nhận và giá trị gốc; hàng bị từ chối vẫn giữ raw, candidate `None` cùng lỗi cụ thể.

## Hợp đồng request SSI ứng viên

GET `https://api.ssi.com.vn/api/v3/data/ohlc`, tham số `symbol=SSI`, `from=2026/10/19 00:00:00`, `to=2026/10/19 23:59:59`, `timeFrame=1m`, `pageIndex=1`, `pageSize=10` mặc định ở inspector. Client provider mặc định page size 1000. Builder tạo cận bao gồm trọn ngày lịch; chưa chứng minh SSI thực sự áp dụng tính bao gồm đó. Chỉ gửi `ascending=true` khi yêu cầu qua native `intraday-ohlc`; canonical dataset vẫn từ chối ascending như trước. Cần xác minh sort, tính bao gồm cận và envelope trước promotion. Không thêm timeframe/endpoint hay fallback nguồn đã retire.

Provider và inspector dùng chung `ohlc_1m_params`. Chuyển ngày trước I/O; cận sai/đảo và tham số paging không dương bị từ chối. `--max-pages` giới hạn lần thử trang dữ liệu, mặc định 100 (hợp lệ 1–1000). Retry HTTP có giới hạn riêng; pages_requested đếm lần thử trang logic, không phải số HTTP retry/auth.

## Pagination và lỗi

Route 1m tải liên tiếp từ `--page-index` (mặc định 1), **không** dừng ở trang có ít hàng nhưng không rỗng. Khi không có page count dùng được, phải lấy trang kết thúc rỗng tường minh; có `pagesCount` thì kiểm tra trang cuối được khai báo. Nếu có `totalRecord`, lần tải từ trang 1 phải khớp số đếm. Các tên metadata nhận diện này có từ inspector cũ, không phải schema SSI mới xác minh. Shape không biết là malformed, không phải dữ liệu rỗng.

Trang lặp (kể cả cùng hàng nhưng đổi thứ tự), page identity sai, total/page count thay đổi, số hàng kết thúc không khớp, trang rỗng quá sớm và chạm giới hạn đều là lỗi rõ ràng. Lỗi HTTP/auth/network/provider/non-JSON giữ các trang/candle đã nhận; body lỗi nhận được vẫn có thể xem. Page-limit/cắt cụt là FAILED, không phải completeness thành công. Tải từ trang >1 được ghi suffix scope, không chứng minh toàn khoảng. `itemsCount` được giữ trong metadata nhưng không tự coi là tổng mọi trang.

Envelope provisional nhận array ở top-level hoặc array data/items/dataList/result trong envelope, lồng giới hạn qua data/result/response. Marker lỗi provider không bị biến thành no-data. Envelope cùng metadata/field chưa dùng vẫn có trong full output.

## Mapping và bảo vệ timestamp

Mapper chung: `src/contracts/intraday_preview.py`, dictionary `src/contracts/mappings/ssi_v3.json` version `1.1.0-preview`, contract `1.0.0`. Adapter và inspector gọi cùng mapper. Không đổi field contract chung hay schema.

| Field chuẩn | Nguồn provisional / xử lý |
| --- | --- |
| symbol | Mã yêu cầu, đối chiếu symbol nguồn nếu có; lệch thì từ chối |
| time | `time` có đủ ngày/giờ nguồn và Z hoặc ±HH:MM; chuẩn hóa UTC, không dịch hay cắt timestamp |
| timeframe | Hằng 1m; timeFrame/timeframe nguồn mâu thuẫn bị từ chối |
| open/high/low/close | Field cùng tên chuyển float hữu hạn; không tự scale; kiểm tra giá dương và bất đẳng thức OHLC |
| volume | Field cùng tên chuyển chính xác số nguyên không âm trong BIGINT; không lấy hiệu volume tích lũy |
| value | `calculate_trade_value` hiện có: int(round(close * volume)); ước tính, không phải turnover chính thức |
| reference_price/ceiling_price/floor_price | NULL: chưa xác minh nguồn/context tương đương; không đọc daily từ DB |

Giá trị optional thiếu vẫn null trong bằng chứng mapping; OHLCV cần cho validation mà thiếu sẽ từ chối candidate thay vì tạo giá trị giả. Field lạ và `value` nguồn vẫn raw/unused. Giá không hữu hạn, boolean, volume lẻ/âm, OHLC sai và value ước tính tràn bị từ chối với diagnostic. Dùng lại hành vi `round` hiện có; không đổi estimator.

**Ngữ nghĩa nguồn BLOCKED:** scale giá sang VND/cổ phiếu, volume có phải số cổ phiếu mỗi nến, timezone của timestamp naive và bar-start hay bar-end. Chuyển numeric cho candidate không chứng nhận đơn vị. Khi chưa có bằng chứng, preview không rỗng tốt nhất chỉ PROVISIONAL. Không có fixture intraday bịa được dùng làm bằng chứng.

Từ chối datetime naive, chỉ ngày, chỉ giờ, epoch/biểu diễn chưa hỗ trợ. Không dùng ngày request tạo timestamp nến. Chưa triển khai ghép ngày/giờ nguồn riêng khi chưa có bằng chứng. Nếu nguồn có ngày riêng cùng timestamp aware, ngày phải khớp timestamp và phạm vi ngày Việt Nam yêu cầu. Giữ metadata bar v2 lịch sử trong definitions.json vì chưa xác minh quy ước v3; metadata đó không chứng minh quy ước bar v3.

## Chất lượng và diễn giải output

Report tách request/pagination, mapping/validation, quan sát cấu trúc và completeness. Có request/trang, số raw/mapped/rejected, thời gian nguồn đầu/cuối theo thứ tự nhận, UTC chuẩn đầu/cuối và cận thời gian thực, số timestamp trùng, đảo thứ tự nhận, lỗi identity/timestamp, field optional thiếu/unsupported, lỗi OHLCV và công thức value ước tính.

Dùng lại `validate_intraday_record`, `validate_intraday_batch`. Warning phiên dùng giờ Việt Nam 09:00–11:30 và 13:00–15:00; bucket phút liên tục để tìm thiếu dùng 09:00–11:29, 13:00–14:29. Không tạo nến giả qua nghỉ trưa, khác ngày hay auction. Giữ nguyên timestamp nguồn cả giây/phần lẻ. Quy ước bar auction đóng cửa chưa rõ; warning là quan sát, không phải bằng chứng phải dịch bar nguồn. Gap có thể không giao dịch hoặc thiếu nguồn. Không giả định số nến cố định.

| Trạng thái cuối | Ý nghĩa / exit tiến trình |
| --- | --- |
| PROVISIONAL | Nhận/map không có lỗi chặn; ngữ nghĩa live chưa rõ; exit 0 |
| EMPTY | Array dữ liệu nguồn rỗng tường minh; chưa chứng minh ngày nghỉ/phiên; exit 0 |
| PARTIAL | Hàng bị từ chối mapping/validation hoặc lỗi trùng nến theo batch; exit 1 |
| FAILED | Lỗi request, malformed, lặp/cắt cụt/giới hạn pagination; exit 1 |
| CLI / request plan sai | Lỗi parser/validation; exit 2 |

PROVISIONAL vẫn có thể kèm warning cấu trúc. Completeness luôn **UNVERIFIED**, độc lập HTTP thành công, kết thúc paging, validation PASS hay exit 0. Validation PASS chỉ cho biết candidate vượt các quy tắc shape số/identity/time đã định nghĩa offline. Không âm thầm sửa hàng lỗi; nến trùng vẫn giữ trong bằng chứng và ngăn claim batch sạch.

## Kiểm tra contract DB (không persist)

Schema hiện tại: `stock_raw_intraday` có unique index symbol/time/data_hash, payload JSONB gốc nullable và provenance source (mặc định SSI). Đây không phải bảng clean phân vùng tháng. `stock_intraday` có primary key `(symbol,timeframe,time)`, partition theo tháng của time, OHLCV/value/context nullable và các cột sẵn có khác. Preview không dùng persistence helper hay query schema, không đổi partition/hàng hoặc relabel provenance lịch sử.

`20260803_add_raw_intraday_payload.sql` cũ áp dụng cho `raw_intraday`; `20260826_standardize_stock_table_names.sql` đổi tên thành `stock_raw_intraday`. Đây là khác biệt tên trong lịch sử migration đã quan sát, không phải lý do tạo/đổi tên bảng ở task này. Chưa xác minh schema/thứ tự triển khai thực tế. Ingest thủ công tương lai phải kiểm tra constraint/partition đang triển khai và đánh giá identity source/hash giữa nguồn lịch sử bằng đề xuất review riêng; preview không cần migration.

## Checklist promotion production — task riêng sau chấp nhận

1. Cấu hình credential SSI và quyền mạng; capture response thật giới hạn cho SSI và mã/ngày thứ hai trên phiên hoàn tất. Không lưu secret vào fixture.
2. Xác minh query key, cận, sort, envelope/metadata và từng ranh giới trang; đối chiếu đầu/cuối và total, không dùng số nến cố định.
3. Xác lập format/timezone/bar-start hoặc end, scale giá và đơn vị volume mỗi nến từ response thật và tài liệu SSI. Giữ block các dạng chưa rõ.
4. Review raw/clean, lỗi, duplicate, bằng chứng phiên/gap và value ước tính. Cần chủ sở hữu chấp nhận mapping.
5. Task riêng kiểm tra chỉ đọc raw/clean key, source/hash provenance, payload/nullable và partition tháng; chỉ đề xuất migration nếu có thay đổi contract production đã chứng minh cần review.
6. Triển khai/review persist thủ công raw trước, clean 1m đã validate sau, idempotent và scope giới hạn; sau đó cho phép promotion registry/CLI riêng. Schedule và backfill lịch sử cần phạm vi/cho phép riêng. Preview không tự thực hiện các bước này.

Migration: none. Data impact: none. Backfill: none. Không kích hoạt feature, signal, backtest hay alert.
