# Hướng dẫn SSI v3 REST inspector

[English](README.md) · [CLI production](../../../docs/CLI_USAGE.vi.md)

## Mục đích và dependency

Chạy mọi lệnh từ thư mục gốc repository. Công cụ READ-ONLY đối với Supabase: không tạo DB client, không persist dữ liệu thị trường. `list` và help chạy local; `run` có thể xác thực/gọi SSI thật. Cài requirements trong venv Python 3.11, cấu hình `SSI_API_KEY`, `SSI_API_SECRET` tại `.env` local; không cần Supabase credential. Không in token hay commit file response chứa dữ liệu tài khoản nhạy cảm.

Inspection không bật ingest production. Stock Daily/Index Daily đã ready; stock-intraday, symbol-list, index-list là capability preview. Master-data inspection là endpoint native, không phải pipeline đồng bộ master đã triển khai. Catalog là snapshot tại lúc query, completeness chưa xác minh, không phải lịch sử catalog theo ngày.

## Lệnh và dataset

Các ví dụ dưới gồm help/list, preview stock/index, xem mapping clean 1m, đối chiếu OHLC daily, catalog, master, pagination và khoảng ngày. Mọi ví dụ `run` đều READ-ONLY — SSI API request. `--full-json` in toàn bộ response nhận được, không lấy mọi trang.

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

Mặc định page-index 1, page-size 10, limit 3, timeout 30 giây. Chỉ lấy một trang được yêu cầu; `--limit` chỉ giới hạn in, không thay page-size hay số request. Với canonical index-summary/securities-by-board/index-list không paging, truyền paging tường minh bị từ chối. Dùng trang cụ thể cho endpoint có paging, không coi một trang là toàn bộ lịch sử. Timeout hợp lệ 1–120, limit không âm; page-index/page-size phải dương. Caveat code: giá trị 0 bị `or` chuyển thành mặc định trước validation, nên tránh 0.

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
