# Feature khối ngoại EOD

Pipeline dẫn xuất độc lập này chỉ đọc `stock_daily`. File calendar JSON đã xác
minh (`source`, `market`, `sessions`) xác định cửa sổ phiên; nếu thiếu, pipeline
trả `WINDOW_UNVERIFIED`. Tiền có đơn vị VND. Ratio là fraction với mẫu số
`total_traded_value`; activity là mua cộng bán và mẫu số ratio là hai lần tổng
giá trị giao dịch. NULL biểu thị field/lịch sử thiếu hoặc mẫu số không hợp lệ,
không phải số 0. Phạm vi matched/deal/odd-lot chính xác của SSI vẫn là limitation.

Fingerprint gồm formula version, calendar identity, phiên kỳ vọng, sự có/mất
row và source value liên quan. Upsert giữ `created_at`; `updated_at` chỉ là thời
điểm ghi, không phải thứ tự source.
