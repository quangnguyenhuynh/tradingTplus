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
độ gần, không phải xác suất tăng. Mọi candidate hợp lệ được xếp hạng
deterministic rồi lấy `top_k` gần nhất (mặc định 30), không lọc bằng threshold;
thiếu `top_k` trả `insufficient_sample`, không padding.

Kết quả gồm xác suất return > 0, median, P25, Wilson interval, baseline cùng mã và
lift. Query, normalization và match/rank được lưu để audit. Calibration bán kính chạy walk-forward và chỉ dùng training interval; không sửa/approve
profile và không phải final evidence. Walk-forward không random split, không cho
future outlier/outcome lọt vào normalization, match, baseline hoặc calibration bán kính.

`analog_quality` tách riêng sample size, `top_k`, bán kính động `d_k` (`d30`
khi mặc định), median, p90 và percentile bán kính walk-forward. P50/P75/P95 tạo
bucket `good`/`usable`/`weak`/`out_of_distribution`; thiếu calibration trả
`unknown`, không tạo percentile giả. Weak/OOD vẫn trả T+ nhưng có warning.
`d_k`/percentile đo tương đồng, không phải xác suất; Wilson interval nằm riêng
trong `statistical_confidence`.

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
V2 vẫn draft, cần history build và validation riêng, không tái sử
dụng evidence V1.

`analogs query` đọc evidence đã persist. Không `--apply` thì chỉ đọc; có `--apply` chỉ audit nguyên tử khi profile exact đã approved. V1 vẫn draft nên query production block với `EXACT_PROFILE_NOT_APPROVED`.

`analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date DD/MM/YYYY --checkpoint EOD --distance-threshold 0.5` chỉ đọc source và tính trong memory, không ghi bảng Analog. Option threshold cũ bị bỏ qua và chỉ giữ để tương thích CLI.

## Vận hành CLI hiện tại (SSI v3)

Cây lệnh thực tế gồm `profiles list|register|sync`, `history build`, `validate`, `approve`, `reject`, `query`, `inspect`, `daily run`. Không có subcommand report riêng. Dùng JSON inspect/validate/query làm báo cáo. Ngày tại đây bắt buộc DD/MM/YYYY. Profile bất biến theo code/version/config hash; có nguồn V1 và V2. Xem hash nguồn bằng đăng ký dry-run trước khi đăng ký DB.

Đăng ký profile không apply là dry-run local, không cần credential. Profile list đọc `analog_profiles`. History build đọc clean daily/feature và dựng snapshot/outcome; không apply chỉ đọc DB/tính toán, apply ghi `analog_snapshots`, `analog_outcomes`. Full/incremental theo cơ chế persist hiện có; replace còn cần `--confirm-replace`, có thể xóa đúng phạm vi profile/mã/ngày. Không dùng hash của profile/version khác.

Inspect: READ-ONLY — database read kèm tính nghiên cứu, bắt buộc distance threshold tường minh. Query và daily run là luồng phân tích có gate, mặc định READ-ONLY; khi được phép và có apply là WRITE — explicit apply. Có thể lưu bằng chứng query/match (`analog_queries`, `analog_query_matches`), không tạo tín hiệu giao dịch. Approve/reject cần validation-run ID thật, reviewer và reason; mặc định dry-run, apply có thể ghi review/registry (`analog_profile_reviews`, `analog_profiles`). Ví dụ dưới cố ý dùng dry-run. UUID review minh họa phải thay bằng ID run hợp lệ đã có.

**Điểm BLOCKED trong vòng đời:** parser nhận `validate --apply` nhưng handler không truyền apply, không persist kết quả calibration/walk-forward vào `analog_validation_runs`. Review cần hàng validation đã tồn tại. Vì vậy chỉ CLI chưa hoàn thành vòng đời validation/approval mới; exit 0 không chứng minh validation được lưu. Calibration cần `--final-test-start`; threshold tùy chọn chỉ là ứng viên thử, không phải khuyến nghị production. Query có thể trả `blocked` trước khi tạo DB client nếu source profile chưa được approve. Không có lệnh nào bỏ qua gate approval.

Chỉ so một mã với lịch sử trước đó của chính mã ấy tại cùng checkpoint EOD. Outcome phải quan sát được tại ngày query; validation theo thời gian với baseline cùng mã/checkpoint, không chia ngẫu nhiên hay gộp mã. `insufficient_sample` là kết quả hợp lệ, không được tự mở rộng universe. Xem [đặc tả Historical Analog](../../../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md) để biết hợp đồng bằng chứng.

```bash
python main.py analogs profiles list
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1
python main.py analogs profiles sync --profile TPLUS_ANALOG_CORE_EOD --version 1
python main.py analogs history build --profile TPLUS_ANALOG_CORE_EOD --version 1 --config-hash d19417afed8718337c12aae7a668dd68e0f323dbb9c2316c92a5122759e9751b --symbols SSI --from 05/01/2026 --to 19/10/2026 --mode incremental
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 05/01/2026 --to 30/09/2026 --run-type calibration --final-test-start 01/10/2026 --thresholds 0.5 1.0
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/10/2026 --to 19/10/2026 --run-type validation
python main.py analogs validate --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --from 01/10/2026 --to 19/10/2026 --run-type final
python main.py analogs inspect --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 19/10/2026 --checkpoint EOD --distance-threshold 1.0
python main.py analogs query --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbol SSI --date 19/10/2026
python main.py analogs daily run --profile TPLUS_ANALOG_CORE_EOD --version 1 --symbols SSI --date 19/10/2026
python main.py analogs approve --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run 00000000-0000-0000-0000-000000000001 --reviewer operator --reason "Review existing final evidence"
python main.py analogs reject --profile TPLUS_ANALOG_CORE_EOD --version 1 --validation-run 00000000-0000-0000-0000-000000000001 --reviewer operator --reason "Evidence incomplete"
```

[English](README.md) · [CLI](../../../docs/CLI_USAGE.vi.md)

### Đăng ký profile có ghi — chỉ sau khi duyệt dry-run

Đây là WRITE — explicit apply vào analog_profiles, cần DB; không phải lệnh kiểm tra tài liệu.

```bash
python main.py analogs profiles register --profile TPLUS_ANALOG_CORE_EOD --version 1 --apply
```
