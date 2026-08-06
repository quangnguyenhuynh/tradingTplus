# Signal - fixed-rule research đang đóng băng

Code hiện tại tạo daily candidate và scan feature đã đóng theo exact strategy
version/config được approve. Đường này chạy được nhưng đã bị thay thế; không phải
signal production được chấp nhận.

Không chạy write hoặc mở rộng luồng này cho Phase 1 mới. Historical analog Phase
1 chỉ trả phân tích, chưa tạo signal. Xem
[spec đang dùng](../../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).
