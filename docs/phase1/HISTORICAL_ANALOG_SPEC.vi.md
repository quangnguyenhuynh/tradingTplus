# Trading T+ - Spec Historical Analog Phase 1

Trạng thái: **hợp đồng thiết kế; chưa triển khai code**  
Thay thế: hướng strategy/rule cố định và approve rule trong thư mục này.

## Quyết định

Phase 1 không bắt đầu bằng rule mua/bán. Ở mỗi checkpoint, hệ thống mô tả trạng
thái hiện tại của **một mã**, tìm các trạng thái lịch sử tương tự của **chính mã
đó**, rồi trả phân phối outcome H+.

```text
feature an toàn thời điểm của SSI lúc 13:30
  -> bucket và hợp đồng matching đã version
  -> snapshot lịch sử SSI tương tự lúc 13:30
  -> phân phối outcome H+1 / H+3 / H+5
  -> kết quả phân tích hiện tại chỉ-đọc
```

Core profile tuyệt đối không pool dữ liệu nhiều mã. SSI không được dùng lịch sử
HPG, FPT hoặc mã khác để tăng số mẫu. Không đủ quan sát tương tự của SSI thì trả
`insufficient_sample`.

## Hợp đồng input an toàn thời điểm

- Checkpoint: 09:30, 11:30, 13:30, 14:30 theo Asia/Ho_Chi_Minh.
- Feature daily chỉ dùng phiên giao dịch đã hoàn tất trước đó.
- Feature intraday chỉ dùng nến 15m/60m đã đóng, aggregate từ 1m clean
  `stock_intraday`; không dùng nến đang chạy.
- `stock_daily` là trục phiên giao dịch và nguồn outcome future close. Dữ liệu
  thiếu, stale, chưa đủ, tạm ngừng hoặc endpoint không hỗ trợ phải bị loại, không
  đổi thành 0.
- Mỗi snapshot phải lưu lineage/availability và identity profile để test
  look-ahead có thể tái lập.

## Profile matching

Profile bất biến theo `profile_code + version + config_hash`. Profile khai báo
checkpoint, dimension feature bắt buộc, bucket fixed/categorical hoặc quantile
chỉ học trong training, missing/freshness rule, fallback deterministic, minimum
effective sample theo từng mã, entry/cost/outcome model và điều kiện validation
theo thời gian.

`group_key` chỉ là nhãn deterministic cho trạng thái đã bucket của một mã;
không phải nhóm gom cổ phiếu. Fallback dimension phải khai báo trước. Runtime
không được nới boundary hoặc bỏ dimension sau khi đã thấy outcome.

## Evidence và validation

Snapshot lịch sử chỉ được evaluate khi đã quan sát đủ horizon H+. Với từng tập
match cùng mã, tính sample/effective sample, xác suất return dương, phân phối
return, median/mean, downside quantile, MAE/MFE và target/stop nếu profile có
định nghĩa. Dùng observed trading sessions và entry-price convention cố định.

Validation phải theo thời gian: lựa chọn training đứng trước validation/test và
statistic dùng cho snapshot sau chỉ lấy evidence hợp lệ trước đó. So với baseline
cùng mã, cùng checkpoint. Approve/reject **phương pháp profile**, không approve
rule mua. Backtest/approval strategy cũ không là evidence cho phương pháp này.

## Runtime và phạm vi

Đến checkpoint, runtime chỉ đọc feature và statistics đã build/approve, tìm match
cùng mã và tối đa ghi audit analysis. User mở app không làm chạy lại full
backtest.

Output Phase 1 chỉ là phân tích: xác suất, return/risk, số mẫu, confidence hoặc
“chưa đủ evidence”. Signal, alert, %NAV, đặt lệnh, AI tự chọn feature và mô hình
gom nhiều mã đều ngoài scope.

## Thứ tự triển khai

1. Contract snapshot an toàn thời điểm và test.
2. Profile immutable, snapshot lịch sử cùng mã, outcome và statistics.
3. Validation OOS theo thời gian và approval profile.
4. Runtime lookup read-only và audit record.

Không command Phase 1 nào tự gọi ingest, feature, signal hoặc alert. Artifact
strategy/backtest legacy được giữ dormant để audit/tái sử dụng có chủ đích, không
repurpose âm thầm.
