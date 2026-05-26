# tradingTplus

Pipeline thu thập dữ liệu SSI -> Supabase, sau đó tính feature kỹ thuật và sinh trading signal.

## Cấu trúc repo

- `main.py`: CLI entrypoint cho các tác vụ ingest.
- `src/ssi/`: client gọi SSI API.
- `src/pipeline/`: luồng `init`, `daily`, `backfill`, `fetch_one_day`.
- `src/database/`: Supabase client + các hàm insert/upsert.
- `src/engine/feature_engine.py`: tính indicator/features.
- `src/engine/signal_engine.py`: sinh signal từ features.
- `scripts/`: script hỗ trợ kiểm tra kết nối API/DB và chạy sample backfill.

## Quick start

1. Cài dependencies:

```bash
pip install -r requirements.txt
```

2. Tạo `.env` với các biến:

```bash
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
SSI_CONSUMER_ID=
SSI_CONSUMER_SECRET=
```

3. Chạy pipeline:

```bash
python main.py init
python main.py backfill 2024-01-01 2024-12-31
python main.py daily
python main.py daily 20/05/2026
python main.py test SSI 20/05/2026
```

## Scripts hỗ trợ

```bash
python scripts/check_ssi_api.py
python scripts/check_supabase.py
python scripts/check_symbols.py
python scripts/backfill_sample.py
```

## Ghi chú vận hành

- `daily` và `backfill` mặc định theo múi giờ VN (UTC+7).
- `backfill` yêu cầu format `YYYY-MM-DD`.
- Khi parse timestamp intraday lỗi, hệ thống sẽ bỏ qua candle lỗi thay vì ghi dữ liệu sai thời gian.

## Trạng thái flow hiện tại

- ✅ Ingest: `init`, `backfill`, `daily`, `test` đã chạy được qua `main.py`.
- ✅ Feature: có engine tính indicator và lưu vào bảng `features`.
- ✅ Signal: có engine sinh tín hiệu rule-based và lưu `trading_signals`.
- ⚠️ Backtest: chưa có engine backtest chính thức (file `backtest_engine.py` đang để placeholder).

## Lỗi 42P10 khi upsert `raw_intraday`

Nếu log báo `there is no unique or exclusion constraint matching the ON CONFLICT specification (42P10)` với `on_conflict=symbol,time,data_hash`, cần tạo unique index tương ứng trong Postgres/Supabase:

```sql
create unique index if not exists raw_intraday_symbol_time_data_hash_uidx
on public.raw_intraday(symbol, time, data_hash);
```

Code hiện tại đã có fallback tự động bỏ `on_conflict` để job không bị dừng, nhưng để hết lỗi hẳn và đảm bảo idempotent đúng nghĩa, bạn nên tạo unique index như trên.


## Schema DB hiện repo đang dùng

Đã bổ sung tài liệu chi tiết ở file `docs_db_schema.md` gồm:
- danh sách bảng code đang đọc/ghi,
- cột tối thiểu cần có theo từng bảng,
- unique index khuyến nghị theo `on_conflict`,
- SQL kiểm tra schema/index hiện tại.

## Snapshot cập nhật gần nhất

- Xem tài liệu tổng hợp mới nhất: `REPO_STATUS_2026-05-26.md`.
