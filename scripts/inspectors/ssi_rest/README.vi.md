# Hướng dẫn SSI v3 REST inspector

[English](README.md) · [CLI production](../../../docs/CLI_USAGE.vi.md)

## Mục đích và dependency

Chạy mọi lệnh từ thư mục gốc repository. Công cụ READ-ONLY đối với Supabase: không tạo DB client, không persist dữ liệu thị trường. `list` và help chạy local; `run` có thể xác thực/gọi SSI thật. Cài requirements trong venv Python 3.11, cấu hình `SSI_API_KEY`, `SSI_API_SECRET` tại `.env` local; không cần Supabase credential. Không in token hay commit file response chứa dữ liệu tài khoản nhạy cảm.

Inspection không bật ingest production. Stock Daily/Index Daily đã ready; stock-intraday, symbol-list, index-list là capability preview. Master-data inspection là endpoint native, không phải pipeline đồng bộ master đã triển khai. Catalog là snapshot tại lúc query, completeness chưa xác minh, không phải lịch sử catalog theo ngày.

## Lệnh và dataset

Các ví dụ dưới gồm help/list, preview stock/index, xem mapping clean 1m, đối chiếu OHLC daily, catalog, master, pagination và khoảng ngày. Mọi ví dụ `run` đều READ-ONLY — SSI API request. `--full-json` in mọi trang OHLC 1m đã tải; endpoint khác vẫn chỉ in response của lần gọi.

```bash
python scripts/inspectors/ssi_rest/inspect.py --help
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run --help
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --date 2026-10-19 --data-source ssi_v3 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run index-daily --index-code VNINDEX --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --limit 5 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run daily-ohlc --symbol SSI --date 2026-10-19 --ascending
python scripts/inspectors/ssi_rest/inspect.py run symbol-list --board HOSE --limit 5
python scripts/inspectors/ssi_rest/inspect.py run index-list --limit 5
python scripts/inspectors/ssi_rest/inspect.py run master-data --from-date 2026-10-01 --to-date 2026-10-19 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run stock-daily --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-index 2 --page-size 20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run index-daily --index-code VNINDEX --from-date 2026-10-01 --to-date 2026-10-19 --limit 3
python scripts/inspectors/ssi_rest/inspect.py run securities-by-board --symbol SSI
python scripts/inspectors/ssi_rest/inspect.py run securities-by-board --index-code VN30
python scripts/inspectors/ssi_rest/inspect.py run securities-summary --symbol SSI --date 2026-10-19
python scripts/inspectors/ssi_rest/inspect.py run index-summary --index-code VNINDEX --date 2026-10-19
```
| CLI dataset | Native endpoint | Selector | Dates / Ngày | Paging |
| --- | --- | --- | --- | --- |
| stock-daily | securities-summary | --symbol SSI | --date / --from-date + --to-date | Yes / Có |
| stock-intraday | intraday-ohlc | --symbol SSI | --date / --from-date + --to-date | Yes / Có |
| index-daily | index-summary | --index-code VNINDEX | --date / --from-date + --to-date | No / Không |
| symbol-list | securities-by-board | --board HOSE | None / Không | No / Không |
| index-list | index-list | optional / tùy chọn --board | None / Không | No / Không |

## Native endpoint và alias tương thích

Base URL duy nhất: `https://api.ssi.com.vn/api/v3`. Các endpoint native: `access-token` (POST `/auth/token`), `securities-by-board` (`/data/securitiesByBoard`), `securities-summary` (`/data/securitiesSummary`), `index-list` (`/data/indexList`), `index-summary` (`/data/indexSummary`), `daily-ohlc` và `intraday-ohlc` (cùng `/data/ohlc`, timeFrame 1d/1m), `master-data` (`/data/masterdata`).

`securities-by-board` chọn đúng một trong symbol/board/index-code. `securities-summary` chọn symbol hoặc index-code và ngày/khoảng. Native `index-summary` chọn board hoặc index-code và chỉ một ngày. `master-data` nhận ngày/khoảng; raw có thể xem dù chưa có clean mapping.

Các alias lookup không phải endpoint v3 độc lập:

| Alias | Native | Selector |
| --- | --- | --- |
| securities | securities-by-board | --board hoặc --market |
| securities-details | securities-by-board | --symbol |
| index-components | securities-by-board | --index-code |
| daily-stock-price | securities-summary | --symbol + ngày |
| daily-index | index-summary | --index-code + ngày |

`run all` chạy bảy native data endpoint (không auth riêng, không lặp alias); có thể tạo nhiều request và mỗi endpoint có selector khác nhau. Ưu tiên từng dataset để kiểm soát phạm vi.

## Ngày, paging, giới hạn

Ngày nhận DD/MM/YYYY hoặc YYYY-MM-DD. Chọn `--date` hoặc đủ `--from-date`, `--to-date`; không ghép cả hai. Canonical index-daily range tạo một request mỗi ngày lịch, tối đa 100 request; không tự chứng minh mỗi ngày là phiên. Catalog từ chối mọi ngày; symbol-list bắt buộc board. Canonical catalog nhận --market/--exchange như alias board, nhưng các giá trị phải thống nhất. Canonical stock/index từ chối board/market/exchange và ascending; chỉ native OHLC hỗ trợ `--ascending`.

Mặc định page-index 1, page-size 10, limit 3, timeout 30 giây. Ngoài OHLC 1m, chỉ lấy một trang được yêu cầu; `--limit` chỉ giới hạn in, không thay page-size hay số request. Với canonical index-summary/securities-by-board/index-list không paging, truyền paging tường minh bị từ chối. Dùng trang cụ thể cho endpoint có paging, không coi một trang là toàn bộ lịch sử. Timeout hợp lệ 1–120, limit không âm; page-index/page-size phải dương. Page-index/page-size bằng 0 hoặc âm bị từ chối trước truy cập service.

## Raw, clean, mapping và lỗi

Report in dataset/source đã chọn, endpoint/URL/params đã che bí mật, HTTP status, thời gian, kiểu response, vị trí danh sách, số hàng nhận/in, paging metadata, sample raw và sample clean khi có mapping. `--show-mapping` thêm quy tắc field và preview-only field; `--full-json` thêm raw đầy đủ, clean và diagnostic đầy đủ. Missing required/optional, unused source fields và errors giúp phân biệt API thành công với mapping thành công. Field chưa xác minh để null; endpoint không có mapping chỉ xem raw.

File mapping thực tế ở `src/contracts/mappings/ssi_v3.json`. Chuỗi log cũ `src/data_contracts/mappings/...` chưa được sửa trong task tài liệu; đó không phải đường dẫn hiện tại.

Exit 0 khi không có FAILED (PASS hoặc EMPTY), exit 1 khi request/HTTP/auth/mapping thất bại, exit 2 khi parser hoặc canonical request plan không hợp lệ. Lỗi native option có thể được bắt thành FAILED/exit 1. Empty không chứng minh coverage; PASS không chứng minh DB persist. 401/403 cần kiểm tra cặp key/secret v3 và entitlement, timeout cần thu hẹp phạm vi, mapping failure cần giữ raw và diagnostic. Không retry bằng nguồn đã retire; không tự sửa mapping/nguồn trong task tài liệu.

Chỉ kiểm tra parser/plan và test mock offline cho các ví dụ; không gọi SSI/Supabase thật để validate hướng dẫn.

## Toàn bộ tham số run

| Tham số / alias | Bắt buộc | Mặc định | Giá trị / số lượng |
| --- | --- | --- | --- |
| `endpoint` | có | `—` | 1 |
| `--data-source` | không | `"ssi_v3"` | ssi_v3 |
| `--symbol` | không | `—` | 1 |
| `--date` | không | `—` | 1 |
| `--from-date` | không | `—` | 1 |
| `--to-date` | không | `—` | 1 |
| `--board` | không | `—` | 1 |
| `--market` | không | `—` | 1 |
| `--exchange` | không | `—` | 1 |
| `--index-code` | không | `—` | 1 |
| `--page-index` | không | `—` | 1 |
| `--page-size` | không | `—` | 1 |
| `--limit` | không | `3` | 1 |
| `--full-json` | không | `false` | flag |
| `--show-mapping` | không | `false` | flag |
| `--timeout` | không | `30` | 1 |
| `--ascending` | không | `—` | flag |

## Preview intraday SSI v3 nhiều trang (chỉ đọc)

Route `stock-intraday`/native `intraday-ohlc` của REST inspector nay dùng adapter preview chung và tải mọi trang từ trang bắt đầu đến kết thúc tường minh hoặc lỗi/giới hạn. `--limit` chỉ giới hạn in; `--full-json` bao gồm mọi trang raw đã nhận và clean candidate. `--max-pages` mặc định 100 (1–1000); chạm giới hạn, trang lặp, total không khớp hay lỗi request trả FAILED/exit 1 và giữ bằng chứng đã nhận. Không đổi các route daily/index/catalog một-trang của inspector.

Mẫu SSI live do chủ sở hữu cung cấp cho 2026-10-20 xác nhận `ohlc.tradingDate` dạng `YYYY/MM/DD HH:mm:ss`, field `ohlc.value` và terminal `{"code":204,"msg":"No Content"}`. Diễn giải tường minh đúng format nguồn này theo `Asia/Ho_Chi_Minh`, rồi chuyển UTC; vẫn hỗ trợ dạng có offset hợp lệ. Alias `time` cũ vẫn bắt buộc timezone. Từ chối chỉ ngày/chỉ giờ và dạng naive khác; không tạo ngày từ request hay dịch phút.

Canonical v3 `value` là **SSI-reported intraday candle value** (giá trị nến intraday SSI trả về), parse chính xác số nguyên không âm trong signed BIGINT, không qua float. **Không ước tính hoặc tính bù**. Nguồn thiếu/null/rỗng giữ NULL kèm SOURCE_VALUE_MISSING; sai định dạng/không hữu hạn/lẻ/âm/tràn bị từ chối. Zero giữ nguyên zero. Report tách nguồn có value, numeric hợp lệ, mapping giữ nguyên và xác minh độc lập ý nghĩa thị trường (vẫn false).

Envelope 204/No Content đã xác nhận chỉ kết thúc paging OHLC 1m khi không có payload/marker lỗi mâu thuẫn và đã qua kiểm tra metadata/số đếm. Giữ nguyên raw envelope, termination provider_no_content_204. Trang ngắn không rỗng không tự kết thúc; trang lặp, total sai, malformed/lỗi và cắt cụt do giới hạn vẫn fail. --limit chỉ giới hạn in; --full-json giữ các trang raw đã nhận, candidate và diagnostic.

Ngày được cung cấp có 226 hàng unique trên 23 trang không rỗng rồi trang 24, thứ tự giảm dần, 135 nến sáng/90 chiều/một nến 14:45. Đây là quan sát do chủ sở hữu báo cho riêng ngày đó, không phải số count hay công thức chung. Chỉ có hai object candle thật và terminal envelope được cung cấp; replay offline xác minh 2/2, không tái tạo các hàng còn thiếu. Agent live rerun: NOT_RUN (thiếu credential). Bar-start/end, ý nghĩa value/turnover độc lập và completeness thị trường còn chưa xác minh. Ingest/schedule production vẫn tắt; preview không đọc/ghi DB.

Xem [runbook và checklist](../../../docs/STOCK_INTRADAY_PIPELINE.vi.md) để biết mapping từng field, paging, validation/session/gap, giới hạn nguồn và cách promotion riêng.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-19 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --from-date 2026-10-01 --to-date 2026-10-19 --page-size 100 --max-pages 100 --limit 5
python scripts/inspectors/ssi_rest/inspect.py run intraday-ohlc --symbol SSI --date 2026-10-19 --ascending --limit 5
```

`--max-pages`: số trang dữ liệu OHLC 1m tối đa, mặc định 100, hợp lệ 1–1000; không thay page-size/limit.

```bash
python scripts/inspectors/ssi_rest/inspect.py list
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --show-mapping
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --full-json
python scripts/inspectors/ssi_rest/inspect.py run stock-intraday --symbol SSI --date 2026-10-20 --page-size 10 --max-pages 100 --limit 5
```

## Mapping catalog chứng khoán — 27/10/2026

symbol_list SSI v3 version 1.1.0-preview map symbolNameVi→stock_name, board→market/exchange, stockType→security_type. Optional thiếu giữ NULL, type lạ giữ text nguồn. Contract daily/intraday/index không đổi. PASS chỉ kiểm tra row mapping, không chứng minh đủ board/universe hoặc ghi DB. [Bằng chứng và provenance fixture](../../../docs/SSI_V3_MASTER_EVIDENCE.vi.md).
