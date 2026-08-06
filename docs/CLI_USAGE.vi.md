# Sử dụng CLI

## Luồng strategy Phase 1 explicit
Cấu hình `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`; chạy migration `20260804` rồi `20260806`. Ngày CLI có dạng `DD/MM/YYYY`. Backtest, daily setup và scan mặc định dry-run chỉ đọc và in JSON; thêm `--write` mới ghi. Approval luôn là lệnh ghi audit, bắt buộc owner và notes không rỗng.

```bash
python main.py strategies list
python main.py strategies backtest --strategy BREAKOUT_V1 --version 1 --from 01/01/2024 --to 31/12/2025 --symbols SSI HPG
python main.py strategies approve --strategy BREAKOUT_V1 --version 1 --backtest-run UUID --decision approve --owner Quang --notes "Đã xem H+1/H+3/H+5"
python main.py signals daily-setup --strategy BREAKOUT_V1 --version 1 --date 04/08/2026 --target-session 05/08/2026 --symbols SSI HPG --write
python main.py signals scan --strategy BREAKOUT_V1 --version 1 --date 05/08/2026 --slot 09:30 --symbols SSI HPG --write
```
Backtest dùng trục phiên tạm `observed_stock_daily_v1`, không đoán ngày lễ. `--output-dir DIR` tạo `summary.json`, `signals.csv`, `review.md` deterministic. JSON có status, dry_run, scope/identity exact, metrics và signal_count. Exit code: 0 thành công, 1 lỗi chạy, 2 tham số sai. Kiểm tra row bằng filter exact strategy/version/config/date trong sáu bảng Phase 1. Không cần backfill market data hay feature.
