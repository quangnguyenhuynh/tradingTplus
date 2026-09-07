# Feature và báo cáo khối ngoại EOD

Luồng độc lập là `stock_daily -> lệnh foreign feature -> stock_foreign_features_daily -> RPC`;
ingest không tự gọi feature. Nguồn duy nhất là field DailyStockPrice trong
`stock_daily`, không có REST endpoint ForeignTrading riêng.

Với W=5/20 phiên đã xác minh: net=`SUM(N)`, activity=`SUM(B+S)`, net
ratio=`SUM(N)/SUM(V)`, activity ratio=`SUM(B+S)/(2*SUM(V))`, với
V=`total_traded_value`. Buy/sell days đếm N>0/N<0. Change 5D lấy cửa sổ hiện tại
trừ năm phiên liền trước, không overlap. Tiền là VND; ratio là fraction; nhân 100
để hiển thị % hoặc điểm phần trăm cho change. NULL là thiếu/không hợp lệ, không
phải zero. Activity là tổng hai phía, không quảng bá là turnover duy nhất. Phạm
vi matched/deal/odd-lot chính xác của SSI chưa được xác minh độc lập.

Calendar JSON phải có `source`, `market`, `sessions` và do operator xác minh.
Không suy lịch từ weekday hay row của mã. Thiếu lịch trả `WINDOW_UNVERIFIED`;
thiếu phiên nguồn trả `MISSING_SOURCE`; lịch sử được chứng minh chưa đủ trả
`INSUFFICIENT_HISTORY`. Không persist row giả. Fingerprint gồm version, calendar,
phiên kỳ vọng, sự có/mất row và source value. Sửa source ngày D có thể ảnh hưởng
D và tối đa 19 phiên sau.

Scope mặc định là danh sách active hiện tại (`current_active_symbols`), không
phải universe lịch sử toàn sàn. RPC dùng cùng một ngày cho mọi mã. Preview,
check, rank và history read-only; rank/history gọi chính RPC chung cho CLI,
web/Flutter. RPC `SECURITY INVOKER`; anon bị thu hồi, authenticated đọc/thực thi,
service role ghi. Cần kiểm tra SELECT/RLS hiện có của `symbols` và `stock_daily`.

## Runbook thủ công

1. Chạy migration `20260907_create_stock_foreign_features_daily.sql`.
2. Kiểm tra daily và calendar cho scope nhỏ.
3. Chạy `foreign-features-preview` với `--calendar-file`.
4. Backfill scope nhỏ bằng `foreign-features-backfill`.
5. Chạy `foreign-features-check`.
6. Query `foreign-rank` và `foreign-symbol`.
7. Chỉ mở rộng scope sau khi kiểm tra source/calendar/coverage/quyền.

Verification và rollback ở cuối migration. Nếu source thiếu, dùng CLI
`backfill-daily` đúng symbol/date sau khi operator duyệt; feature không tự sửa
source. Luồng job tương lai là `stock-eod -> daily check -> foreign feature ->
foreign check -> report`, luôn là các bước độc lập.
