# SSI v3 Intraday 1m — runbook chỉ đọc

[English](STOCK_INTRADAY_PIPELINE.md) · [CLI](CLI_USAGE.vi.md) · [Báo cáo xác minh](SSI_V3_INTRADAY_PREVIEW_REPORT.vi.md)

## Phạm vi và bằng chứng

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest/schedule production vẫn tắt; preview không đọc/ghi DB.


## Chạy an toàn

Chạy tại root repository trong venv Python 3.11 đã cài requirements. Cấu hình SSI_API_KEY, SSI_API_SECRET local; không cần Supabase credential. Help/list chạy local. Fixture mẫu không chứa credential. Các lệnh đã kiểm tra parser/plan offline; đây là lệnh để chủ sở hữu xác minh chỉ đọc tiếp theo.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

Không thêm lệnh CLI. Native intraday-ohlc hiện có dùng cùng adapter/mapper provider. Production intraday-ingest, stock-intraday, backfill-intraday, backfill kết hợp và refill vẫn NOT_IMPLEMENTED trước service. Clean 1m lịch sử vẫn có thể dùng cho feature độc lập; preview không kích hoạt feature.

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

Report có field time/diễn giải thực tế, số raw/mapped/rejected, trang request/nhận, terminal reason, cận raw/UTC và chronology, duplicate, thứ tự nhận giữ nguyên, lỗi OHLCV/identity và warning cấu trúc. Giữ thứ tự giảm dần từ nguồn; warning đảo so với view tăng dần tự nó không chứng minh dữ liệu hỏng. Dùng validator phiên/gap hiện có; nghỉ trưa/auction/no-trade không tạo nến giả. Completeness luôn UNVERIFIED.

source_value_present_count: API có value khác null/rỗng; source_value_numeric_valid_count: parse số nghiêm ngặt pass; source_value_mapped_count: candidate clean thực sự giữ value. source_value_missing_count và source_value_invalid_count tách riêng; source_value_semantics_verified=false nghĩa là chưa chứng nhận độc lập ý nghĩa official matched turnover. Warning thiếu value ngoài sample in vẫn hiển thị.

PROVISIONAL (không rỗng, sạch) và EMPTY exit 0; mapping/batch PARTIAL hoặc request/paging FAILED exit 1; CLI/plan sai exit 2. Không trạng thái nào chứng minh production readiness hay completeness thị trường. --show-mapping in quy tắc/bằng chứng; --full-json có mọi trang raw đã nhận cùng candidate/lỗi theo vị trí. Không đổi chuỗi/thứ tự/value nguồn.

## Contract DB và guard persistence tương lai

Không gọi DB. stock_raw_intraday giữ identity symbol/time/data_hash, source và payload gốc nullable; stock_intraday giữ khóa symbol/timeframe/time, value BIGINT nullable và partition time theo tháng. Migration payload cũ gọi raw_intraday; migration chuẩn hóa sau đổi thành stock_raw_intraday. Không cần đổi tên/key/schema ở đây.

src/database/client.py:upsert_intraday vẫn gọi calculate_trade_value khi value thiếu/NULL. Không đổi hành vi legacy hoặc consumer hiện có. **Trước promotion v3, phải có guard persistence theo nguồn: mang nguyên value được trả về, giữ NULL không fallback, từ chối value sai và chứng minh không gọi estimator.** Không đơn thuần truyền NULL vào helper persistence hiện tại: nó sẽ tính ước lượng. Sửa giá trị ước lượng lịch sử phải là thao tác riêng có scope mã/ngày/provenance và cho phép tường minh; task này không làm.

Bước promotion tiếp theo cần chủ sở hữu review lần chạy chỉ đọc mới, đầy đủ raw/clean/value và page/duplicate check; làm rõ độc lập bar/value semantics khi cần; xác minh constraint/partition/provenance triển khai; task persist thủ công có scope cùng guard value riêng. Task này không bật registry/CLI/schedule/backfill.

Migration: none. Ghi DB/sửa lịch sử: none. Backfill: none. Không feature/signal/backtest/alert.
