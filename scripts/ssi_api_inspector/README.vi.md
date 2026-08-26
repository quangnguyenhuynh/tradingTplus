# Trình kiểm tra SSI REST API

CLI read-only dùng để kiểm tra trực tiếp SSI FastConnect Data REST trong Phase 0.

Công cụ này gửi request HTTP trực tiếp tới SSI, in response envelope thật ở dạng dễ đọc, và không ghi vào Supabase hay bất kỳ database nào. Dùng công cụ này để xác minh endpoint có hoạt động không, tham số request, phân trang, response rỗng, khóa dữ liệu, field trong record, và khác biệt giữa các endpoint SSI trước khi thay đổi pipeline ingest hoặc clean data.

## Giới thiệu

SSI REST API Inspector phục vụ giai đoạn Phase 0 của Trading T+: xây dựng hạ tầng dữ liệu và kiểm chứng dữ liệu nguồn trước khi tính feature, signal, backtest hoặc gợi ý giao dịch.

Mục tiêu chính:

- Kiểm tra contract thực tế của SSI REST API bằng request thật.
- Quan sát response envelope, field, paging, mã lỗi và dữ liệu mẫu.
- Hỗ trợ đối chiếu giữa các endpoint như `DailyStockPrice`, `DailyOhlc`, `IntradayOhlc`.
- Giữ việc kiểm tra API tách biệt khỏi ingest, database, feature, signal và backtest.

Tính an toàn:

- Chỉ đọc đối với trạng thái database.
- Không import `SupabaseClient`.
- Không insert, update, upsert hoặc delete dữ liệu.
- Tự lấy SSI access token khi gọi endpoint cần xác thực.
- Tự retry xác thực một lần nếu SSI trả HTTP `401`.
- Redact consumer credential, bearer token, authorization header và các khóa giống token trước khi in output.
- Không tính feature, signal hoặc kết quả backtest.

Không chia sẻ nguyên văn toàn bộ output CLI một cách tùy tiện. Dù token đã được redact, response SSI vẫn có thể chứa ngữ cảnh về thị trường, mã chứng khoán hoặc tài khoản.

## Cài đặt

Chạy các lệnh từ project root.

Chuẩn bị Python environment của project và cài dependencies hiện có. Ví dụ:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Trên Windows PowerShell, kích hoạt môi trường bằng:

```powershell
.venv\Scripts\Activate.ps1
```

Cách cài đặt môi trường thực tế có thể khác ví dụ trên. Nếu project đã có virtual environment, hãy dùng lại environment đó.

## Cấu hình `.env`

Inspector đọc cấu hình hiện có của project từ environment variables. Thêm các biến sau vào file `.env` của project hoặc export trong shell hiện tại:

```env
SSI_CONSUMER_ID=your_consumer_id
SSI_CONSUMER_SECRET=your_consumer_secret
```

Không đưa credential thật, token thật hoặc nội dung `.env` lên GitHub.

Không cần Supabase credential vì inspector không truy cập database.

## Quick Start

Liệt kê tất cả tên endpoint mà CLI hỗ trợ:

```bash
python scripts/ssi_api_inspector/inspect.py list
```

Kiểm tra một endpoint:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --limit 3
```

Kiểm tra tất cả data endpoint được hỗ trợ với cùng một nhóm tham số chung:

```bash
python scripts/ssi_api_inspector/inspect.py run all \
  --symbol SSI \
  --market HOSE \
  --exchange HOSE \
  --index-code VNINDEX \
  --date 10/07/2026 \
  --page-size 20 \
  --limit 3
```

`run all` không chạy report độc lập cho `access-token`. Client vẫn tự lấy token khi endpoint cần xác thực.

## Cú pháp CLI

```text
python scripts/ssi_api_inspector/inspect.py list

python scripts/ssi_api_inspector/inspect.py run <endpoint> [options]
```

Dùng help tích hợp để kiểm tra contract CLI hiện tại:

```bash
python scripts/ssi_api_inspector/inspect.py --help
python scripts/ssi_api_inspector/inspect.py run --help
```

## Các endpoint

| Tên CLI | HTTP method | SSI endpoint | Tham số chính |
| --- | --- | --- | --- |
| `access-token` | POST | `AccessToken` | JSON `consumerID`, `consumerSecret` |
| `stock_securities` | GET | `Securities` | `Market`, `PageIndex`, `PageSize` |
| `securities-details` | GET | `SecuritiesDetails` | `Market`, `Symbol`, `PageIndex`, `PageSize` |
| `index-components` | GET | `IndexComponents` | `IndexCode`, `PageIndex`, `PageSize` |
| `index-list` | GET | `IndexList` | `Exchange`, `PageIndex`, `PageSize` |
| `daily-ohlc` | GET | `DailyOhlc` | `Symbol`, `FromDate`, `ToDate`, paging, tùy chọn `ascending=true` |
| `intraday-ohlc` | GET | `IntradayOhlc` | `Symbol`, dates, `resolution=1`, paging, tùy chọn `ascending=true` |
| `daily-index` | GET | `DailyIndex` | `IndexCode`, `FromDate`, `ToDate`, paging |
| `daily-stock-price` | GET | `DailyStockPrice` | `Symbol`, dates, `Market`, paging |

Theo kiến trúc hiện tại của Trading T+:

- `DailyStockPrice` là nguồn daily chính cho nghiên cứu T+/swing.
- `DailyOhlc` chỉ dùng để đối chiếu, không phải nguồn daily canonical.
- `IntradayOhlc` được gọi với `resolution=1` vì raw intraday chỉ lưu dữ liệu 1 phút.
- Dữ liệu 5 phút, 15 phút và 60 phút phải được aggregate sau trong feature pipeline; không fetch hoặc lưu các timeframe đó như raw data ở đây.
- Các field giao dịch nước ngoài được kiểm tra từ `DailyStockPrice`; đặc tả public REST mà project dùng không định nghĩa endpoint `ForeignTrading` độc lập.
- Kiểm tra orderbook/market depth qua public REST nằm ngoài CLI này. Hãy dùng utility streaming/snapshot được hỗ trợ riêng nếu cần.
- Không hardcode một con số cố định như 226 nến để kết luận intraday đầy đủ cho mọi ngày giao dịch.

## Các option

| Option | Mặc định | Mô tả |
| --- | --- | --- |
| `--symbol` | `SSI` | Mã cổ phiếu dùng cho các endpoint theo symbol. |
| `--date` | `10/07/2026` | Ngày rõ ràng theo định dạng `DD/MM/YYYY`. Được dùng cho cả `FromDate` và `ToDate`. |
| `--market` | `HOSE` | Market cho `stock_securities`, `securities-details` và `daily-stock-price`. |
| `--exchange` | `HOSE` | Exchange cho `index-list`. |
| `--index-code` | `VNINDEX` | Mã chỉ số cho `index-components` và `daily-index`. |
| `--page-index` | `1` | Số trang của SSI API. |
| `--page-size` | `10` | Số record yêu cầu SSI trả về. |
| `--limit` | `3` | Số record mẫu tối đa được in trong report. |
| `--full-json` | tắt | In toàn bộ response envelope đã redact. |
| `--timeout` | `30` | HTTP timeout tính bằng giây. |
| `--ascending` | không gửi | Gửi `ascending=true` tới các OHLC endpoint có hỗ trợ. |

### `--page-size` khác `--limit` như thế nào?

Hai option này kiểm soát hai việc khác nhau:

- `--page-size` quyết định request sẽ yêu cầu SSI trả về bao nhiêu record.
- `--limit` quyết định CLI sẽ in bao nhiêu record phát hiện được trong mục `Sample records`.
- `--full-json` in toàn bộ response envelope đã redact và không bị giới hạn bởi sample limit.

Ví dụ:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-size 100 \
  --limit 5
```

Lệnh này yêu cầu SSI trả tối đa 100 record, nhưng chỉ in 5 record đầu tiên trong phần sample.

### `--ascending`

Khi bỏ qua `--ascending`, CLI không gửi tham số `ascending`.

Khi bật option này, CLI gửi:

```text
ascending=true
```

CLI hiện tại không có flag `--descending` và không gửi rõ `ascending=false`.

## Ví dụ sử dụng

### AccessToken

Dùng để kiểm tra xác thực và xem token envelope đã redact:

```bash
python scripts/ssi_api_inspector/inspect.py run access-token --full-json
```

Token thật và credential thật không được xuất hiện trong output.

### Securities

Liệt kê securities theo market:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-index 1 \
  --page-size 20 \
  --limit 5
```

Dùng paging để xem trang khác:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-index 2 \
  --page-size 20 \
  --limit 5
```

### SecuritiesDetails

Kiểm tra một symbol:

```bash
python scripts/ssi_api_inspector/inspect.py run securities-details \
  --market HOSE \
  --symbol SSI \
  --full-json
```

### IndexList

Kiểm tra danh sách index theo exchange:

```bash
python scripts/ssi_api_inspector/inspect.py run index-list \
  --exchange HOSE \
  --page-size 50 \
  --limit 10
```

### IndexComponents

Kiểm tra thành phần của một index:

```bash
python scripts/ssi_api_inspector/inspect.py run index-components \
  --index-code VNINDEX \
  --page-size 100 \
  --limit 10
```

### DailyStockPrice

Kiểm tra endpoint daily stock-price canonical:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --full-json
```

Dùng endpoint này để xác minh daily OHLC, volume, value, field giao dịch nước ngoài và các field thực tế khác do SSI trả về trước khi chỉnh mapper ingest daily.

### DailyOhlc

Kiểm tra `DailyOhlc` để so sánh với `DailyStockPrice`:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-ohlc \
  --symbol SSI \
  --date 10/07/2026 \
  --ascending \
  --full-json
```

Không xem endpoint này là nguồn daily canonical trừ khi kiến trúc project được thay đổi rõ ràng.

### IntradayOhlc

Kiểm tra record intraday OHLCV 1 phút:

```bash
python scripts/ssi_api_inspector/inspect.py run intraday-ohlc \
  --symbol SSI \
  --date 10/07/2026 \
  --page-size 1000 \
  --limit 10 \
  --ascending
```

CLI luôn gửi `resolution=1` cho endpoint này.

Không giả định một số cố định như 226 nến là đầy đủ cho mọi ngày giao dịch. Cần kiểm tra cấu trúc phiên, ngắt giao dịch, paging của SSI, hành vi endpoint và khả năng có dữ liệu lịch sử cho ngày được yêu cầu.

### DailyIndex

Kiểm tra dữ liệu daily index:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-index \
  --index-code VNINDEX \
  --date 10/07/2026 \
  --full-json
```

### Run all data endpoints

```bash
python scripts/ssi_api_inspector/inspect.py run all \
  --symbol SSI \
  --market HOSE \
  --exchange HOSE \
  --index-code VNINDEX \
  --date 10/07/2026 \
  --page-index 1 \
  --page-size 20 \
  --limit 3
```

Các giá trị option chung được truyền vào endpoint builder có sử dụng chúng. Option không liên quan tới endpoint cụ thể sẽ bị builder của endpoint đó bỏ qua.

## Đọc kết quả

Với mỗi endpoint, CLI in các thông tin sau:

- Nhãn endpoint và tên CLI.
- HTTP method và URL.
- Request parameter đã redact.
- HTTP status code.
- Thời gian request.
- Response content type.
- Top-level response keys hoặc top-level response type.
- Các giá trị SSI envelope phổ biến nếu có, gồm `status`, `message`, `responseCode` và `totalRecord`.
- Vị trí data list được phát hiện.
- Số record phát hiện được.
- Keys của record đầu tiên.
- Các path giống token được phát hiện trong response.
- Sample records đã redact.
- JSON đầy đủ đã redact nếu bật `--full-json`.

Inspector tìm list dữ liệu ở các vị trí phổ biến như:

```text
data
dataList
items
```

Nếu response là dictionary, inspector cũng fallback sang list top-level đầu tiên tìm thấy.

## Trạng thái kết quả

### `PASS`

Inspector tìm thấy một record list và list đó có ít nhất một record.

`PASS` nghĩa là endpoint trả về dữ liệu có thể phát hiện được. Trạng thái này không chứng minh mọi field, ngày, record hoặc giá trị đều đúng.

### `EMPTY`

Inspector không tìm thấy record nào trong list được phát hiện.

Nguyên nhân có thể gồm:

- Cuối tuần hoặc ngày nghỉ thị trường.
- Không có dữ liệu cho ngày lịch sử được yêu cầu.
- Symbol không hợp lệ hoặc không được hỗ trợ.
- Market, exchange hoặc index code không đúng.
- Page được yêu cầu vượt quá số record hiện có.
- SSI trả envelope shape khác.
- Endpoint trả HTTP success nhưng data list rỗng.

`EMPTY` không đồng nghĩa API bị lỗi. Không chuyển response API rỗng thành dữ liệu thị trường giá trị 0 trừ khi có business rule riêng đã được kiểm chứng rõ ràng.

### `FAILED`

Endpoint phát sinh `InspectorError`, ví dụ do xác thực, mạng, timeout, response không hợp lệ hoặc xử lý HTTP failure trong client.

Khi chạy `run all`, CLI tiếp tục endpoint kế tiếp rồi in summary.

## Exit code

- Exit code `0`: không endpoint nào có status `FAILED`.
- Exit code `1`: có ít nhất một endpoint có status `FAILED`.

Endpoint `EMPTY` hiện không làm process trả exit code `1`. Khi cần đánh giá dữ liệu có tồn tại hay không, hãy đọc summary được in ra thay vì chỉ dựa vào process exit code.

Ví dụ:

```bash
python scripts/ssi_api_inspector/inspect.py run all --date 10/07/2026
echo $?
```

## Troubleshooting

### Thiếu credential

Kiểm tra biến môi trường có tồn tại trong cùng shell chạy Python hay không:

```bash
python -c "from src.config import config; print(bool(config.SSI_CONSUMER_ID), bool(config.SSI_CONSUMER_SECRET))"
```

Lệnh này chỉ in boolean. Không in giá trị credential thật.

### HTTP 401

Client tự lấy token mới và retry một lần sau HTTP `401` đối với authenticated request.

Nếu vẫn lỗi:

- Kiểm tra `SSI_CONSUMER_ID` và `SSI_CONSUMER_SECRET`.
- Kiểm tra tài khoản SSI còn hoạt động và có quyền gọi endpoint hay không.
- Kiểm tra API host hoặc credential có thay đổi không.
- Không thêm vòng retry vô hạn.

### Response rỗng

Thử một ngày giao dịch lịch sử đã biết và kiểm tra identifier theo endpoint:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --full-json
```

Kiểm tra `message`, `responseCode`, `totalRecord`, vị trí data list được phát hiện và toàn bộ envelope đã redact.

Cuối tuần, ngày nghỉ, response SSI rỗng hoặc endpoint không được hỗ trợ phải được giữ là dữ liệu thiếu. Không tạo row giả.

### Record count bất thường

Kiểm tra paging trước khi kết luận dữ liệu thiếu:

```bash
python scripts/ssi_api_inspector/inspect.py run intraday-ohlc \
  --symbol SSI \
  --date 10/07/2026 \
  --page-index 1 \
  --page-size 1000 \
  --limit 5
```

So sánh `totalRecord`, record count trong response hiện tại, page size và page index. Không hardcode một candle count duy nhất làm chuẩn completeness cho mọi ngày.

### Output quá lớn

Bỏ `--full-json`, giảm `--limit`, hoặc giảm `--page-size`:

```bash
python scripts/ssi_api_inspector/inspect.py run securities \
  --market HOSE \
  --page-size 10 \
  --limit 2
```

### Python import error

Chạy script từ project root với project environment đã được kích hoạt:

```bash
pwd
python scripts/ssi_api_inspector/inspect.py list
```

Không chạy bản copy standalone của `inspect.py`, vì script phụ thuộc vào package file và `src.config` trong repository này.

## Validation

Chạy test offline tập trung:

```bash
pytest -q tests/test_ssi_api_inspector.py
```

Test suite kiểm tra các nội dung như:

- Registry endpoint được hỗ trợ.
- Tham số request cốt lõi.
- Shape JSON cho POST authentication.
- Cách dùng bearer token và deep redaction.
- Giới hạn sample record.
- Redaction khi in full JSON.
- Phát hiện response rỗng.
- Reauthentication một lần sau HTTP `401`.
- Summary và exit code của `run all`.
- Inspector package không import hoặc gọi database write.

Để chạy live SSI smoke test, dùng symbol và ngày giao dịch lịch sử rõ ràng. Live smoke test cần SSI credential hợp lệ và vẫn chỉ đọc:

```bash
python scripts/ssi_api_inspector/inspect.py run daily-stock-price \
  --symbol SSI \
  --market HOSE \
  --date 10/07/2026 \
  --limit 1
```

## Current limitations

- Option ngày hiện chỉ biểu diễn một ngày cụ thể và được dùng cho cả `FromDate` và `ToDate`.
- Intraday resolution cố định là 1 phút.
- CLI chưa có option rõ ràng `--from-date` và `--to-date`.
- CLI chưa có `--descending` hoặc cách gửi rõ `ascending=false`.
- `run all` dùng một nhóm CLI argument chung cho các endpoint-specific builder.
- Inspector chỉ báo cáo API response; không kết luận các row trả về có đầy đủ hoặc đúng ngữ nghĩa để ingest hay không.
- Inspector không ghi raw table hoặc clean table.
- Inspector không kích hoạt feature, signal hoặc backtest pipeline.

Mọi thay đổi CLI trong tương lai phải giữ hành vi read-only mặc định và nên cập nhật README này, parser test, endpoint test và hướng dẫn troubleshooting trong cùng task.
