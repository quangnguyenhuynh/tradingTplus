# Backtest - fixed-rule research đang đóng băng

Code hiện tại replay evaluator daily/intraday cũ, dùng open nến clean 1m giao
dịch được đầu tiên sau decision time và gắn outcome H+1/H+3/H+5 theo observed
daily sessions. Đây là research chạy được nhưng đã bị thay thế.

Kết quả này không phải evidence cho phương pháp historical analog và không được
dùng approve production. Ý tưởng entry/outcome chỉ được tái sử dụng sau khi có
test availability đúng thời điểm, cùng mã và validation theo thời gian. Xem
[spec đang dùng](../../docs/phase1/HISTORICAL_ANALOG_SPEC.vi.md).
