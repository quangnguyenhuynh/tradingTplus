# Historical Analog Core EOD V1 và V2

`TPLUS_ANALOG_CORE_EOD` mô tả trạng thái **1d EOD** đã kiểm chứng của một mã và
chỉ so với lịch sử trước đó của chính mã đó. Đây là phân tích lịch sử, không phải
backtest giao dịch: không có lệnh, giá vào, chi phí, signal, alert, stop/target,
drawdown danh mục hoặc %NAV.

Snapshot giữ chín dimension; outcome giữ một return thập phân
`close[H]/close[D]-1` cho H+1/H+3/H+5 ở V1 và thêm H+10 ở V2; validation result là
evidence theo thời gian. `0.043` nghĩa là 4.3%. Chín công thức và weight chính
xác nằm trong file JSON version-control và README tiếng Anh. Thiếu/NaN/vô cực,
mẫu số 0, thiếu năm phiên trước hoặc nến có range 0 đều tạo `not_evaluable`,
không đổi thành 0.

Config đầy đủ được canonical-serialize rồi SHA-256. Registry có `draft`,
`validated`, `approved`, `rejected`, `retired`. Approve phải thủ công và trỏ tới
final validation `completed` có đúng hash. Candidate bắt buộc cùng mã,
profile/version/hash, `1d`, `EOD`, nằm trước D và trong năm năm; toàn bộ outcome
phải đã observable tại D. Median/IQR chỉ fit trên lịch sử hợp lệ trước D; IQR 0
bị từ chối. Distance weighted Euclidean; similarity `exp(-distance)*100` chỉ là
độ gần, không phải xác suất tăng. Giữ tối đa 30 row trong threshold; thiếu 30 trả
`insufficient_sample`, không padding.

Kết quả gồm xác suất return > 0, median, P25, Wilson interval, baseline cùng mã và
lift. Query, normalization và match/rank được lưu để audit. Calibration chỉ nhận
threshold candidate explicit và chỉ dùng training interval; không sửa/approve
profile và không phải final evidence. Walk-forward không random split, không cho
future outlier/outcome lọt vào normalization, match, baseline hoặc chọn threshold.

`distance_threshold` V1 hiện **null có chủ đích**. Có thể build/calibrate, nhưng
final validation, approve và production query/daily phải trả
`DISTANCE_THRESHOLD_NULL` cho tới khi threshold nghiên cứu được đóng băng vào
config/hash chính xác.

`full` upsert có scope; `incremental` upsert row mới/bị ảnh hưởng theo watermark;
`replace` chỉ xóa đúng profile/hash/symbol/range và cần cả `--apply` lẫn
`--confirm-replace`. Mọi write mặc định dry-run. Thứ tự vận hành: verified 1d
features → snapshot hôm nay → cập nhật outcome cũ → query của profile approved.
Không command nào gọi ingest, feature, signal, backtest hay alert.

Bảy bảng lần lượt giữ profile, snapshot, outcome, validation, review thủ công,
query và exact match. Mobile không có quyền write. Migration chạy thủ công;
features cũ không cần backfill, còn snapshot/outcome cần build scope explicit.
Các câu lệnh CLI đầy đủ giống README tiếng Anh.

Repo không có web framework. `AnalogReadService` cung cấp service read-only cho
endpoint profile/latest/query tương lai; wiring HTTP được hoãn và GET không được
recompute. V1 loại trừ intraday, pool nhiều mã, gọi SSI, khuyến nghị, P&L/fee,
alert, ranking và NAV.

## Lệnh runtime production

V1 chỉ hỗ trợ EOD/`1d`. `analogs profiles register` là dry-run nếu thiếu `--apply`; list và register thật dùng `analog_profiles` với đúng identity trong source. `analogs history build` đọc phân trang feature 1d và `stock_daily`; chỉ `--apply` mới upsert snapshot và outcome H+1/H+3/H+5. Replace còn bắt buộc `--confirm-replace` và chỉ xóa đúng identity/mã/khoảng ngày/EOD.

V2 giữ nguyên dimension/matching và lưu H+10 thành row thứ tư trong
`analog_outcomes` với `horizon_sessions=10`, không thêm column. Resolver bắt buộc
đúng code/version, có thể kiểm tra exact hash và không tự chọn version mới nhất.
V2 vẫn draft/threshold null, cần history build và validation riêng, không tái sử
dụng evidence V1.

`analogs query` đọc evidence đã persist. Không `--apply` thì chỉ đọc; có `--apply` chỉ audit nguyên tử khi profile exact đã approved và threshold là số. V1 vẫn draft/threshold null nên query production chủ động block với `EXACT_PROFILE_NOT_APPROVED` và `DISTANCE_THRESHOLD_NULL`.

`analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD --distance-threshold 0.5` chỉ đọc source và tính trong memory, không ghi bảng Analog. Threshold là tham số research tạm thời, không đổi profile/hash, không phải evidence approval, signal hay khuyến nghị đầu tư.
