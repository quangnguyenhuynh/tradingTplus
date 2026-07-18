# SSI streaming inspector

CLI chỉ đọc dùng để kiểm tra dữ liệu streaming SSI FastConnect Data trong Phase 0 thông qua classic SignalR.

## Tài liệu

- [English](README.md)
- [Tiếng Việt](README.vi.md)

## Mục đích

Tool này kết nối tới SSI streaming, subscribe các channel được chỉ định rõ ràng, giải mã message `Broadcast`, đối chiếu field thực tế với registry nội bộ và in diagnostic đã được che thông tin nhạy cảm.

Tool chỉ phục vụ kiểm chứng dữ liệu và không ghi vào Supabase.

Các mục tiêu chính:

- Kiểm tra negotiate và kết nối SignalR.
- Kiểm tra channel SSI có nhận được message hay không.
- Xem cấu trúc payload thực tế của từng loại stream.
- So sánh field thực tế với danh sách field kỳ vọng.
- Phát hiện frame lỗi hoặc payload không giải mã được.
- Hỗ trợ kiểm tra read-only, không làm thay đổi dữ liệu hệ thống.

## Phạm vi an toàn

- Không ghi dữ liệu vào database.
- Không gọi pipeline ingest, feature, signal hoặc backtest.
- Không in secret hoặc token nguyên bản.
- Chỉ subscribe những channel được tạo từ tham số CLI hoặc truyền trực tiếp bằng `--channel`.
- Channel kết thúc bằng `:ALL` chỉ chạy khi người dùng chủ động truyền vào và có thể tạo lượng output rất lớn.

## Yêu cầu

Chạy lệnh từ thư mục gốc của repository.

```bash
cd tradingTplus
```

Kích hoạt virtual environment và cài dependency của project nếu chưa có.

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Tool sử dụng cấu hình SSI streaming hiện có trong project. Các biến môi trường cần thiết phải được khai báo trong `.env` theo cấu hình của `src.config` và `src.ssi.streaming`.

Không commit `.env`, token hoặc secret lên GitHub.

## Quick start

Liệt kê các loại stream đang hỗ trợ:

```bash
python scripts/ssi_streaming_inspector/inspect.py list
```

Chỉ kiểm tra bước negotiate:

```bash
python scripts/ssi_streaming_inspector/inspect.py negotiate
```

Kiểm tra quote cho mã SSI:

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI
```

Kiểm tra index VNINDEX:

```bash
python scripts/ssi_streaming_inspector/inspect.py run index --index-codes VNINDEX
```

## Cú pháp CLI

```text
python scripts/ssi_streaming_inspector/inspect.py list

python scripts/ssi_streaming_inspector/inspect.py negotiate [--timeout SECONDS]

python scripts/ssi_streaming_inspector/inspect.py run KIND \
  [--symbols SYMBOL [SYMBOL ...]] \
  [--index-codes INDEX [INDEX ...]] \
  [--timeout SECONDS] \
  [--max-messages COUNT] \
  [--limit COUNT] \
  [--full-json] \
  [--raw-frames] \
  [--channel EXACT_CHANNEL] \
  [--negotiate-only]
```

## Các command

### `list`

Liệt kê toàn bộ loại stream, prefix channel, loại target và số field kỳ vọng.

```bash
python scripts/ssi_streaming_inspector/inspect.py list
```

Các loại stream hiện hỗ trợ:

| KIND | Prefix channel | Target | Ý nghĩa |
|---|---|---|---|
| `securities-status` | `F` | symbol | Trạng thái giao dịch của chứng khoán |
| `quote` | `X-QUOTE` | symbol | Market data quote |
| `trade` | `X-TRADE` | symbol | Market data trade |
| `foreign-room` | `R` | symbol | Dữ liệu room và giao dịch nước ngoài |
| `index` | `MI` | index code | Dữ liệu chỉ số |
| `realtime-bar` | `B` | symbol | Nến realtime |
| `all` | nhiều prefix | symbol và index code | Chạy lần lượt toàn bộ loại stream |

### `negotiate`

Chỉ chạy bước SignalR negotiate và in kết quả đã được sanitize.

```bash
python scripts/ssi_streaming_inspector/inspect.py negotiate
```

Có thể đặt timeout:

```bash
python scripts/ssi_streaming_inspector/inspect.py negotiate --timeout 15
```

Lưu ý: trong code hiện tại, tham số `--timeout` của command `negotiate` được parser chấp nhận nhưng bước negotiate vẫn sử dụng hành vi timeout của client hiện tại.

### `run`

Kết nối, subscribe channel và lắng nghe message cho một loại stream.

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI
```

## Giải thích option

### `KIND`

Loại stream cần kiểm tra.

Giá trị hợp lệ:

```text
securities-status
quote
trade
foreign-room
index
realtime-bar
all
```

### `--symbols`

Danh sách mã chứng khoán dùng cho các stream theo symbol.

Mặc định:

```text
SSI
```

Ví dụ:

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI FPT VNM
```

Channel được tạo tương ứng:

```text
X-QUOTE:SSI
X-QUOTE:FPT
X-QUOTE:VNM
```

### `--index-codes`

Danh sách mã chỉ số dùng cho stream `index`.

Mặc định:

```text
VNINDEX
```

Ví dụ:

```bash
python scripts/ssi_streaming_inspector/inspect.py run index --index-codes VNINDEX VN30
```

### `--timeout`

Tổng thời gian lắng nghe của mỗi loại stream, tính bằng giây.

Mặc định:

```text
30
```

Ví dụ:

```bash
python scripts/ssi_streaming_inspector/inspect.py run trade --symbols SSI --timeout 60
```

Nếu chạy ngoài giờ giao dịch hoặc mã không phát sinh dữ liệu, nên tăng timeout trước khi kết luận stream không hoạt động.

### `--max-messages`

Số Broadcast payload tối đa cần nhận trước khi dừng.

Mặc định:

```text
3
```

Ví dụ:

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --max-messages 10
```

### `--limit`

Alias của `--max-messages`.

Khi truyền `--limit`, giá trị này sẽ ghi đè `--max-messages`.

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --limit 5
```

### `--full-json`

In payload chi tiết hơn.

Khi không bật option này, tool loại một số phần dữ liệu mẫu lớn khỏi output để dễ đọc hơn.

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --full-json
```

### `--raw-frames`

In thêm từng frame SignalR thô đã được decode.

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --raw-frames
```

Khi kết hợp với `--full-json`, output có thể rất dài.

### `--channel`

Subscribe chính xác một channel thay vì để tool tự tạo channel từ `KIND`, `--symbols` hoặc `--index-codes`.

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --channel X-QUOTE:SSI
```

Option này phù hợp khi cần xác minh chính xác tên channel SSI.

Không tự ý dùng channel `*:ALL` trong kiểm tra thông thường.

Ví dụ channel có thể tạo output rất lớn:

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --channel X-QUOTE:ALL
```

Tool sẽ in cảnh báo khi channel kết thúc bằng `:ALL`.

### `--negotiate-only`

Khi đi cùng command `run`, tool chỉ chạy negotiate rồi thoát, không kết nối để subscribe stream.

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --negotiate-only
```

## Ví dụ sử dụng

### Kiểm tra securities status

```bash
python scripts/ssi_streaming_inspector/inspect.py run securities-status \
  --symbols SSI \
  --timeout 60 \
  --max-messages 5
```

### Kiểm tra quote của nhiều mã

```bash
python scripts/ssi_streaming_inspector/inspect.py run quote \
  --symbols SSI FPT VNM \
  --timeout 60 \
  --max-messages 10
```

### Kiểm tra trade

```bash
python scripts/ssi_streaming_inspector/inspect.py run trade \
  --symbols SSI \
  --raw-frames \
  --max-messages 5
```

### Kiểm tra foreign room

```bash
python scripts/ssi_streaming_inspector/inspect.py run foreign-room \
  --symbols SSI \
  --timeout 60
```

### Kiểm tra index

```bash
python scripts/ssi_streaming_inspector/inspect.py run index \
  --index-codes VNINDEX \
  --timeout 60 \
  --full-json
```

### Kiểm tra realtime bar

```bash
python scripts/ssi_streaming_inspector/inspect.py run realtime-bar \
  --symbols SSI \
  --timeout 60 \
  --max-messages 10
```

### Chạy toàn bộ loại stream

```bash
python scripts/ssi_streaming_inspector/inspect.py run all \
  --symbols SSI \
  --index-codes VNINDEX \
  --timeout 30 \
  --max-messages 3
```

`all` chạy lần lượt từng loại stream. Vì vậy tổng thời gian có thể lớn hơn `--timeout` do timeout được áp dụng cho từng loại.

## Cách đọc output

### `RAW_FRAME`

Chỉ xuất hiện khi bật `--raw-frames`.

Nội dung cho biết frame SignalR sau khi được decode, bao gồm message, method, args hoặc thông tin frame malformed.

Ví dụ dạng rút gọn:

```text
RAW_FRAME { ... }
```

### `MESSAGE`

Mỗi Broadcast payload hợp lệ sẽ được kiểm tra và in thành một dòng `MESSAGE`.

```text
MESSAGE { ... }
```

Output dùng để xem:

- Loại stream được nhận diện.
- Channel yêu cầu.
- Field có trong payload.
- Field kỳ vọng bị thiếu.
- Field ngoài registry.
- Dữ liệu mẫu đã được sanitize.

### `MALFORMED_FRAME`

Xuất hiện khi frame không thể được decode theo cấu trúc mong đợi.

```text
MALFORMED_FRAME { ... }
```

Cần giữ lại output này khi điều tra thay đổi protocol hoặc format SignalR.

### Thông tin kết nối cuối mỗi lần chạy

Tool luôn in diagnostic cuối cùng, gồm:

- Streaming base URL.
- SignalR path.
- Hub name.
- Receive method.
- Switch method.
- Client protocol.
- Connection ID và token đã qua sanitize.
- Danh sách channel.
- Timeout.
- Số raw frame.
- Số Broadcast payload.
- Trạng thái.

### `SUMMARY`

Sau command `run`, tool in kết quả tổng hợp:

```text
SUMMARY {"overall":"PASS","results":{"quote":"PASS"}}
```

Khi chạy `all`, `results` chứa trạng thái của từng loại stream.

## Trạng thái

### `PASS`

Kết nối và nhận được ít nhất một Broadcast payload cho loại stream đó.

### `EMPTY`

Kết nối và subscribe thành công nhưng không nhận được Broadcast payload trong thời gian chờ.

`EMPTY` không đồng nghĩa endpoint sai. Cần kiểm tra:

- Có đang trong giờ giao dịch không.
- Mã hoặc chỉ số có đang hoạt động không.
- Timeout có quá ngắn không.
- Channel có đúng không.
- Tài khoản SSI có quyền streaming không.

### `PARTIAL`

Chỉ xuất hiện ở kết quả tổng hợp khi chạy nhiều loại stream và kết quả không đồng nhất, ví dụ một stream `PASS`, một stream `EMPTY` hoặc `FAILED`.

### `FAILED`

Không thể negotiate, kết nối, subscribe, listen hoặc xử lý stream do lỗi.

Tool không nuốt exception. Thông tin lỗi được in sau khi đã che dữ liệu nhạy cảm.

## Exit code

| Trạng thái tổng | Exit code |
|---|---:|
| `PASS` | `0` |
| `EMPTY` | `0` |
| `FAILED` | `1` |
| `PARTIAL` | `2` |

`EMPTY` trả exit code `0` vì kết nối có thể hợp lệ nhưng không có message trong khoảng thời gian kiểm tra.

Khi dùng trong CI hoặc script, không nên xem `EMPTY` là bằng chứng dữ liệu streaming đã đầy đủ.

## Lưu ý khi kiểm tra SSI streaming

1. Ưu tiên chạy trong giờ giao dịch để tăng khả năng nhận message.
2. Bắt đầu với một mã thanh khoản cao và một channel cụ thể.
3. Chạy `negotiate` trước nếu nghi lỗi credential, endpoint hoặc SignalR handshake.
4. Tăng `--timeout` trước khi kết luận stream `EMPTY`.
5. Chỉ bật `--raw-frames` hoặc `--full-json` khi cần debug sâu.
6. Không dùng `:ALL` mặc định vì volume output có thể rất lớn.
7. Payload thực tế từ SSI là nguồn cần kiểm chứng; registry chỉ là danh sách field kỳ vọng để so sánh.
8. Không suy diễn field hoặc endpoint không có trong tài liệu và payload thực tế.
9. Streaming inspector không thay thế kiểm tra completeness của raw và clean data trong database.
10. Kết quả từ tool này không tự động kích hoạt ingest, feature, signal hoặc backtest.

## File liên quan

```text
scripts/ssi_streaming_inspector/inspect.py
scripts/ssi_streaming_inspector/registry.py
scripts/ssi_streaming_inspector/output.py
src/ssi/streaming.py
tests/test_ssi_streaming_inspector.py
```

Khi thay đổi CLI, stream registry hoặc output format, cần cập nhật đồng thời `README.md` và `README.vi.md` để hai phiên bản tài liệu luôn thống nhất.
