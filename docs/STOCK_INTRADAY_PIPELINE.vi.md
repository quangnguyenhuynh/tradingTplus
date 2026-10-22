# SSI v3 Intraday 1m — runbook preview và pilot thủ công

[English](STOCK_INTRADAY_PIPELINE.md) · [CLI](CLI_USAGE.vi.md) · [Báo cáo xác minh](SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md)


## Pilot intraday thủ công có guard

`stock-intraday` hỗ trợ đúng một mã và ngày giao dịch Việt Nam tường minh. Mặc định/`--dry-run` là READ-ONLY; chỉ `--write` mới cho phép chuỗi chèn raw → clean có kiểm soát. Cần credential SSI; credential service Supabase cho phép preflight chỉ đọc eligibility/xung đột và bắt buộc khi ghi. Nếu chưa cấu hình DB, dry-run báo `NOT_RUN_NO_CREDENTIALS`, số dự kiến chưa biết và `write_ready=false`.

```bash
python main.py stock-intraday 20/10/2026 --symbols SSI
python main.py stock-intraday 20/10/2026 --symbols SSI --write
```

Lệnh thứ hai **chỉ dành cho chủ sở hữu sau khi kiểm tra dry-run/preflight**. Không nhận khoảng ngày, ALL/wildcard, scope thiếu, nhiều mã hoặc ngày tương lai. Cả hai status trong master phải active. Chỉ nguồn `ssi_v3`, timeframe `1m`; value canonical giữ chính xác `ohlc.value`, thiếu/sai sẽ chặn pilot và không ước tính bù. Hàng giống giữ nguyên; clean khác giá trị hoặc raw xung đột key/source/payload sẽ chặn. Không force overwrite. Xác nhận raw trước clean; ghi dở dang/không rõ kết quả trả exit khác 0, cần kiểm tra đúng scope rồi chạy lại an toàn. Không cam kết transaction xuyên hai bảng. Completeness vẫn UNVERIFIED. Các lệnh ingest/backfill/refill/streaming intraday khác và schedule vẫn tắt. Pilot không chạy feature/signal/backtest.

Xem [báo cáo triển khai](SSI_V3_INTRADAY_MANUAL_REPORT.vi.md) về thứ tự ghi, idempotency, partition, phục hồi và xác minh của chủ sở hữu. Inspector vẫn hoàn toàn chỉ đọc; registry giữ preview, không có factory production chung.

## Phạm vi và bằng chứng

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest tự động/schedule vẫn tắt; inspector preview không đọc/ghi DB.


## Chạy an toàn

Chạy tại root repository trong venv Python 3.11 đã cài requirements. Cấu hình SSI_API_KEY, SSI_API_SECRET local; không cần Supabase credential. Help/list chạy local. Fixture mẫu không chứa credential. Các lệnh đã kiểm tra parser/plan offline; đây là lệnh để chủ sở hữu xác minh chỉ đọc tiếp theo.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

Không thêm lệnh CLI. Native intraday-ohlc hiện có dùng cùng adapter/mapper provider. Intraday-ingest tự động, backfill-intraday, backfill kết hợp và refill vẫn NOT_IMPLEMENTED trước service. Clean 1m lịch sử vẫn có thể dùng cho feature độc lập; preview không kích hoạt feature.

## Request và pagination

GET https://api.ssi.com.vn/api/v3/data/ohlc với symbol, from/to (YYYY/MM/DD 00:00:00 đến 23:59:59), timeFrame=1m, pageIndex/pageSize. Inspector mặc định page index 1, size 10, max-pages 100; client size 1000. Kiểm tra paging dương và tạo cận ngày có thứ tự bao gồm hai đầu trước I/O. Native --ascending vẫn tùy chọn; không ép sort raw. Sort, tính bao gồm cận và nghĩa metadata ngoài bằng chứng đã cung cấp cần xác minh độc lập.

Tải trang liên tiếp đến array rỗng tường minh, pagesCount nhất quán hoặc 204/No Content đã xác minh. Trang đầu No Content là EMPTY, không có candle. 204 malformed/mâu thuẫn là FAILED; không miễn trừ lỗi HTTP/API nói chung. Page identity sai, total/page count thay đổi, kết thúc rỗng sớm, trang lặp/đảo lại, totalRecord cuối không khớp và max-pages đều fail, giữ bằng chứng đã nhận. Metadata terminal cũng phải khớp các trang trước. Bắt đầu sau trang 1 ghi suffix scope. Không hardcode số nến. Giới hạn retry HTTP tách riêng số trang/request logic.

Chỉ path OHLC v3 1m nhận diện 204; không đổi hành vi lỗi Daily/Index. Raw pages giữ cả terminal envelope. Terminal hợp lệ có code 204 (integer hoặc string), message No Content, không payload có dữ liệu/không hỗ trợ và không marker status/error mâu thuẫn. Thiếu message, data không rỗng, lỗi khác hoặc metadata sai bị từ chối.

## Mapping canonical

Dictionary: src/contracts/mappings/ssi_v3.json, mapping 1.2.0-preview, contract version vẫn 1.0.0. Provider adapter và inspector dùng chung src/contracts/intraday_preview.py; engine chung truyền context field nguồn cho transform để diễn giải market-local không lan sang alias time cũ hoặc dataset khác.

| Field | Mapping và validation |
| --- | --- |
| symbol | Request identity đối chiếu symbol trả về |
| time | ohlc.tradingDate → transform riêng nguồn → aware UTC; slash local dùng timezone Việt Nam; ISO offset giữ đúng instant |
| timeframe | Hằng 1m; timeframe nguồn mâu thuẫn bị từ chối |
| open/high/low/close | Số hữu hạn dương cùng tên, giữ bất đẳng thức OHLC; chuỗi gốc vẫn raw |
| volume | Số nguyên chính xác không âm trong BIGINT, không lấy hiệu cumulative |
| value | ohlc.value → parse Decimal/integer chính xác → Python int; không dùng close × volume |
| reference_price/ceiling_price/floor_price | NULL khi chưa xác nhận field/context, không đọc DB |

Parse value nhận integer hoặc chuỗi decimal chính xác có giá trị nguyên (kể cả chuỗi thập phân/khoa học cho kết quả nguyên), từ chối float/bool để tránh số lớn đã mất chính xác. Từ chối không hữu hạn, âm, lẻ, ngoài miền. Null/thiếu/rỗng giữ nullable và cảnh báo, không đổi thành zero hay ước tính. Value hợp lệ giữ nguyên ngay khi khác close × volume.

Candle thật 14:45 được chép map tradingDate 2026/10/20 14:45:00 → 2026-10-20T07:45:00Z, close 19950, volume 2626600, value 52400670000. Candle 14:29 map 07:29:00Z với value 2560650000. Case synthetic close=19950, volume=100, value=1994000 chứng minh không thay value bằng 1995000. Mismatch synthetic không phải bằng chứng thị trường thật.

Giữ giây và microsecond hợp lệ. Ngày thiếu/sai, ngoài phạm vi ngày Việt Nam, identity mâu thuẫn, chỉ giờ/chỉ ngày/epoch và naive chưa hỗ trợ bị từ chối. tradingDate aware đầy đủ được kiểm tra theo instant tại Việt Nam, không cắt ngày viết dưới dạng UTC. Bar-start hay bar-end vẫn chưa xác minh; không tạo nến 14:30–14:44, dịch phút hay nối phiên/ngày.

## Report và chất lượng

Report có field time/diễn giải thực tế, số raw/mapped/rejected, trang request/nhận, terminal reason, cận raw/UTC và chronology, duplicate, thứ tự nhận giữ nguyên, lỗi OHLCV/identity và warning cấu trúc. Giữ thứ tự giảm dần từ nguồn, sort view validation clean; vẫn giữ warning mixed và chặn pilot. Dùng validator phiên/gap hiện có; nghỉ trưa/auction/no-trade không tạo nến giả. Completeness luôn UNVERIFIED.

source_value_present_count: API có value khác null/rỗng; source_value_numeric_valid_count: parse số nghiêm ngặt pass; source_value_mapped_count: candidate clean thực sự giữ value. source_value_missing_count và source_value_invalid_count tách riêng; source_value_semantics_verified=false nghĩa là chưa chứng nhận độc lập ý nghĩa official matched turnover. Warning thiếu value ngoài sample in vẫn hiển thị.

PROVISIONAL (không rỗng, sạch) và EMPTY exit 0; mapping/batch PARTIAL hoặc request/paging FAILED exit 1; CLI/plan sai exit 2. Không trạng thái nào chứng minh production readiness hay completeness thị trường. --show-mapping in quy tắc/bằng chứng; --full-json có mọi trang raw đã nhận cùng candidate/lỗi theo vị trí. Không đổi chuỗi/thứ tự/value nguồn.

## Contract DB: inspector và pilot

Inspector không gọi DB. Pilot thủ công mới dùng các bảng/khóa hiện có qua boundary chèn riêng mô tả dưới đây. Helper legacy `upsert_intraday()` vẫn ước tính khi value thiếu; pilot hoàn toàn không gọi helper này và chặn missing/null value trước ghi. Không sửa provenance/value lịch sử. Registry vẫn preview; CLI chỉ mở pilot một mã/ngày. Schedule/backfill và ingest tự động vẫn tắt. Không cần migration hoặc backfill; Codex không chạy live DB writes.

## Persistence và phục hồi pilot thủ công

Workflow hiện có chỉ gọi `src/ingest/stock_intraday/manual.py`. Ingest chung vẫn tắt; registry giữ preview, không có intraday production factory. Pilot tái sử dụng `SSIV3Adapter.preview_intraday()` từ trang 1 cho toàn ngày, cùng retry/paging có giới hạn và 204 hiện có. Chấp nhận tăng/giảm dần nghiêm ngặt; chỉ sort view validation của dữ liệu giảm dần, giữ raw và thứ tự gốc. Mixed và timestamp trùng chặn ghi. Mọi candle phải map đúng identity/ngày, OHLCV hợp lệ và source value nguyên chính xác không thiếu; không lọc hàng lỗi để ghi batch dở.

Eligibility chỉ đọc đúng hàng `symbols` được yêu cầu, cần `status=active` và `intraday_status=active`. Thiếu/không rõ/inactive chặn trước fetch nếu có DB. Không tự active, không mở rộng universe. Guard scope chạy trước khi tạo client. Nguồn rỗng/ngày nghỉ chặn ghi, không tạo candle. Dry-run thiếu DB chỉ xác minh nguồn, không chứng nhận eligibility/xung đột.

Ví dụ ngày Việt Nam 2026-10-20: query `symbol=SSI`, UTC `time >= 2026-10-19T17:00:00Z`, `time < 2026-10-20T17:00:00Z`; clean thêm `timeframe=1m`. Đọc DB theo trang 100 hàng, đối chiếu exact count, giới hạn 10.000 hàng; count thiếu/thay đổi hoặc chạm giới hạn sẽ chặn. Không dùng ngày lịch UTC. Timestamp clean thừa trong scope cũng chặn trước ghi. Không đụng mã/ngày/timeframe khác.

Dựng đủ cả hai payload trước mutation đầu tiên. Raw chỉ dùng symbol/time/OHLCV/data_hash/payload/source/fetched_at hiện có; source `value` nguyên bản nằm trong payload. Hash SHA-256 từ JSON UTF-8 canonical (key sort, separator compact), không chứa thời gian fetch/header transport. Gán audit timestamp tường minh. Khóa raw `(symbol,time,data_hash)` không có source: cùng key nhưng khác source/payload/raw values sẽ chặn. Hash lịch sử khác key candidate giữ nguyên; raw count toàn scope có thể lớn hơn số hàng nguồn khớp.

Clean dùng khóa `(symbol,timeframe,time)`, OHLCV/value và audit timestamp hiện có, chỉ `1m`. `value` nguyên nguồn đi đường riêng hoàn toàn không gọi `upsert_intraday()` hoặc fallback ước tính. Thiếu/null/sai value chặn trước cả hai lớp ghi; không đổi contract nullable chung hay caller khác. Clean giống canonical được skip, không gán lại provenance không biết. Khác bất kỳ field canonical nào chặn toàn bộ preflight. Audit timestamp không tham gia equality/hash.

Thứ tự ghi:

1. Hoàn tất fetch/map/validation, eligibility và cả hai kiểm tra xung đột.
2. Chèn raw bằng `ignore_duplicates=True`, đọc lại đúng scope, so mọi key/payload/source dự kiến.
3. Kiểm tra lại eligibility và xung đột clean. Chỉ gọi RPC `create_partition_if_not_exists` cho tháng UTC thực sự cần chèn clean; dry-run và rerun no-op không tạo partition.
4. Chèn clean bằng `ignore_duplicates=True`. Hàng xung đột xuất hiện đồng thời không bị ghi đè; đọc lại sẽ phát hiện khác biệt.
5. Đọc lại hai scope, xác nhận raw dự kiến và clean timestamp/count/canonical values. Consistency PASS vẫn đi cùng completeness UNVERIFIED. Gap/session warning chỉ là quan sát, không chứng minh thiếu dữ liệu hoặc yêu cầu 226 candle chung.

Mỗi request DB có một lần thử ở tầng ứng dụng; chạy lại tường minh để phục hồi kết quả chưa rõ. Hai lớp là HTTP write riêng, không atomic xuyên bảng. Raw thành công rồi clean/partition/readback lỗi trả PARTIAL, exit khác 0 và failed stage. Số chèn gồm các batch đã được xác nhận; `insert_counts_confirmed=false` cảnh báo request lỗi có thể đã commit thêm. Giữ evidence, kiểm tra đúng mã/ngày, xử lý xung đột rồi chạy lại cùng lệnh. Raw giống được skip, clean thiếu được chèn; không cleanup/delete/overwrite. Rerun thành công là no-op. Writer độc lập vẫn có thể đổi dữ liệu sau final readback; dừng chúng khi owner xác minh. Pilot không update hàng có sẵn.

## Chủ sở hữu xác minh sau merge

Codex không chạy live Supabase writes. Không cần migration, sửa lịch sử hay backfill. Sau khi cấu hình SSI/Supabase service local, owner chạy lệnh chỉ đọc phía trên; xem eligibility, pagination toàn ngày, rejected/duplicate/missing/invalid value bằng 0, timestamp canonical, conflict, planned counts và warning. Sau đó mới chạy lệnh `--write` rồi lặp lại. Yêu cầu consistency raw/clean readback PASS và lần lặp không thêm hàng; lưu ba JSON report. OK/PASS không chứng nhận completeness thị trường. Giữ job tự động tắt. Multi-symbol/history chỉ được làm trong task riêng sau owner validation và có ủy quyền.

Evidence owner cung cấp: SSI 2026-10-20, HPG 2026-10-20, SSI 2026-10-21 mỗi mẫu có 226 raw/226 clean/0 reject, giảm dần, paging kết thúc 204, không trùng hoặc lỗi source value, validation PASS, completeness UNVERIFIED. Đây là quan sát owner, không phải ba full capture hay agent live test.
