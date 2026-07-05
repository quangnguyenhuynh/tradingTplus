# Repo status snapshot (2026-05-26)

Tài liệu này tóm tắt **trạng thái mới nhất của codebase** để chuẩn bị giao task tiếp theo.

## 1) Mục tiêu hệ thống

Repo hiện tập trung vào pipeline:

1. Lấy dữ liệu intraday từ SSI API.
2. Lưu dữ liệu thô vào Supabase/Postgres.
3. Tính feature kỹ thuật.
4. Sinh trading signal rule-based.

Backtest engine đã có MVP để ghép `trading_signals` với `features`, mô phỏng giữ lệnh theo số nến cấu hình và tính metric cơ bản.

## 2) Entrypoint & luồng chạy

- CLI entrypoint: `main.py`
- Lệnh đang có:
  - `python main.py init`
  - `python main.py backfill [from_date] [to_date]`
  - `python main.py daily [DD/MM/YYYY]`
  - `python main.py test [SYMBOL] [DD/MM/YYYY]`

### Daily flow

- `daily_run()` lấy danh sách symbols từ DB.
- Fetch intraday cho từng symbol theo ngày.
- Chạy feature engine ngay sau ingest.

## 3) Các module chính

- `src/ssi/api.py`: gọi SSI API.
- `src/database/client.py`: thao tác Supabase.
- `src/pipeline/`: orchestration ingest (`init_symbols`, `backfill`, `daily_run`, `fetch_one_day`).
- `src/engine/feature_engine.py`: tính feature và ghi bảng `features`.
- `src/engine/signal_engine.py`: sinh và ghi signal.
- `src/engine/data_quality.py`: kiểm tra chất lượng dữ liệu và log.
- `src/engine/backtest_engine.py`: backtest MVP, hỗ trợ cấu hình vốn, tỷ trọng vị thế, số nến nắm giữ, phí và lọc điểm signal.

## 4) Cập nhật DB/migration gần nhất

### `migrations/20260525_expand_features.sql`

- Bổ sung nhiều cột feature cho bảng `features` (EMA/RSI/MACD/volume ratio/VWAP/candle stats...).
- Thêm unique index: `(symbol, timeframe, time)`.

### `migrations/20260525_create_data_quality_logs.sql`

- Tạo bảng `data_quality_logs` để log kiểm tra chất lượng dữ liệu.
- Tạo index theo `(symbol, trading_date)`.

## 5) Gợi ý task tiếp theo (để dễ giao việc)

1. **Backtest refinement**
   - Bổ sung take-profit/stop-loss, multi-position sizing và xuất báo cáo theo symbol/timeframe.
   - Lưu kết quả backtest vào DB để so sánh nhiều cấu hình.

2. **Data quality gate trước signal**
   - Chặn/đánh dấu symbol-date có dữ liệu thiếu nến nghiêm trọng trước khi sinh signal.

3. **Tách config timeframe & universe**
   - Đưa các tham số hard-code (khung thời gian, danh sách mã, ngưỡng rule) về config.

4. **Observability**
   - Chuẩn hóa logging theo run_id + thời gian chạy mỗi step.

5. **Test coverage**
   - Bổ sung unit test cho feature calculator/signal rules và integration test mini flow.

## 6) Trạng thái sẵn sàng giao task

Codebase đã đủ nền tảng để giao ngay các nhóm task:

- Nhóm ingest stability.
- Nhóm feature/signal refinement.
- Nhóm backtest implementation.
- Nhóm data quality & monitoring.

