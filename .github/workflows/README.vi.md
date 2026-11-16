# GitHub Actions — TradingTPlus

## Các workflow EOD đang hoạt động

| Workflow | Lịch giờ Việt Nam | Cron UTC | Ngày dữ liệu được truyền tường minh |
| --- | --- | --- | --- |
| `stock-eod-scheduled.yml` | 17:07 thứ Hai–thứ Sáu | `7 10 * * 1-5` | Chính ngày chạy tại Việt Nam |
| `index-eod-scheduled.yml` | 08:07 thứ Ba–thứ Bảy | `7 1 * * 2-6` | Ngày lịch trước đó tại Việt Nam |

Hai file mới thay thế `stock-eod.yml` và `index-eod-v2.yml` đã nghỉ. GitHub cron dùng **UTC**, Việt Nam UTC+7 và không có DST. GitHub Actions có thể khởi chạy trễ. Để tránh ghi nhầm phiên, job lấy **mốc lịch Việt Nam gần nhất đã qua**, kể cả khi GitHub khởi chạy sau nửa đêm hoặc cuối tuần. Stock dùng ngày của mốc lịch; Index dùng ngày trước mốc lịch. Log ghi `expected_slot_vn`, `runtime_vn`, `target_date`, `target_source`. Nếu job trễ qua **mốc lịch kế tiếp**, chỉ dựa vào giờ chạy thực tế không thể nhận diện chắc chắn phiên gốc, có thể chọn mốc mới; cần kiểm tra log và chạy tay với ngày tường minh để khôi phục phiên bỏ lỡ. GitHub bỏ hẳn cron không được tự khôi phục; không tự backfill hoặc dò ngày lễ. SSI trả rỗng không được tạo dữ liệu giả.

Với lịch tự động, workflow tính ngày mục tiêu và truyền ngày tường minh vào `python main.py stock-eod` hoặc `python main.py index-eod`. Chạy thủ công có nhập `date` dùng đúng ngày nhập; chạy thủ công để trống `date` sẽ gọi CLI **không kèm ngày**, vì vậy giữ nguyên hành vi mặc định của code hiện tại. Không sửa code ingest hoặc `src.ingest.workflows.workflow_dates`.

**Lưu ý:** Đây là **mỗi pipeline chạy một lần cho một phiên**, không phải hai lượt retry của cùng một dataset: Stock chạy chiều phiên T, Index chạy sáng ngày kế tiếp. Lịch giả định thị trường giao dịch thứ Hai–thứ Sáu, không tự kiểm tra ngày lễ, SSI đã đủ dữ liệu hay chưa. Stock EOD vẫn chạy completeness hiện có. Khi cần lấy lại cùng phiên, chạy lại có chủ đích theo ngày; quy tắc ghi lại raw/clean giữ nguyên.

Các workflow khác (`tests.yml`, `stock-intraday.yml`) không đổi trong thay đổi EOD này. Không tự chạy feature/signal/backtest hoặc gọi chéo Stock/Index. `features.yml` chỉ chạy thủ công và không bị các workflow EOD gọi; cách xử lý input của nó được mô tả bên dưới.

## Chạy feature thủ công (`features.yml`)

`features.yml` chỉ chạy bằng `workflow_dispatch` và thực thi `python main.py features --mode <mode>` với đúng default hiện có của CLI. Workflow không ingest dữ liệu nguồn, không sinh signal, không chạy backtest và không gọi workflow EOD.

Cả bốn input dispatch vào shell qua biến môi trường (`DATE_INPUT`, `MODE_INPUT`, `SYMBOLS_INPUT`, `TIMEFRAMES_INPUT`); run block không nội suy trực tiếp `${{ inputs.* }}`, không `eval`, và mọi argv array đều được quote. Symbols/timeframes được tách thành argv array có quote, nên ký tự shell, dấu nháy, `$`, backtick, `;` và glob chỉ là dữ liệu, không phải lệnh.

| Input | Trống / chỉ whitespace | Có giá trị |
| --- | --- | --- |
| `mode` | Dùng `incremental` (giống default của input và CLI) | Luôn truyền `--mode`: `incremental` (default) hoặc `full` |
| `date` | Bỏ `--date`, giữ default hiện có của CLI | Truyền nguyên văn thành một giá trị `--date` |
| `symbols` | Bỏ `--symbols` (CLI default: toàn bộ symbol); không sinh `--symbols` trần | Tách theo space/tab thành các giá trị `--symbols`; không sinh cờ trần |
| `timeframes` | Bỏ `--timeframes`, vì vậy default hiện hành của CLI `15m 60m 1d` được áp dụng; không sinh `--timeframes` trần và không tạo danh sách rỗng | Tách theo space/tab thành các giá trị `--timeframes`; không sinh cờ trần |

Input chứa CR hoặc LF bị từ chối trước khi tách array, nên giá trị nhiều dòng không bao giờ bị cắt im lặng còn dòng đầu. Mọi token symbol/timeframe bắt đầu bằng `-` (và `date`/`mode` mang dạng option) bị từ chối trước khi chạy Python để chống option injection. Symbol, date, timeframe không được hỗ trợ vẫn fail qua validation hiện có của CLI; workflow không thêm regex định dạng symbol/date và không tự áp allow-list timeframe. Nếu Python trả mã lỗi, mã đó được propagate ra job.

Không migration, không sửa DB và không yêu cầu backfill lịch sử trong thay đổi workflow này.
