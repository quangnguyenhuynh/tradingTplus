# Strategy - fixed-rule research đang đóng băng

Code hiện tại triển khai rule hai bước `BREAKOUT_V1` và `PULLBACK_V1`, bất biến
theo version và trả `RuleDecision` để audit. Đây là research legacy chạy được,
không phải thiết kế production Phase 1 đã chốt.

Không thêm strategy, không approve production, không chạy write path và không
dùng metrics backtest cũ làm evidence historical analog. Giữ package để audit
hoặc tái sử dụng có chủ đích cho đến khi có task cleanup riêng. Task Phase 1 mới
phải theo [spec historical analog cùng mã](../../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).
