# DB Schema Overview (from current code usage)

Tài liệu này tóm tắt các bảng Supabase mà code hiện tại đọc/ghi. `schema.sql` là snapshot schema hiện tại; migration history được giữ nguyên để truy vết.

## Phase 0 contracts

- Master data: `symbols`, `securities`, `indexes`, `index_components`.
- Raw data: `raw_daily`, `raw_intraday`, `stream_raw_snapshot`.
- Clean data: `stock_daily`, `stock_intraday` và các streaming snapshot được hỗ trợ.
- Validation: `data_quality_logs`.
- Derived data: một bảng `features`, key `(symbol, timeframe, time)`.

`stock_daily` là nguồn chuẩn cho feature `1d`. `stock_intraday` chỉ lưu nến clean `1m`; feature `15m` và `60m` được aggregate trong memory rồi ghi vào `features`. Ingest không tự tính feature, và feature không tự chạy downstream logic.

## Legacy signal/backtest cleanup

Code và schema signal/backtest MVP legacy đã bị xóa. Migration `migrations/20260731_drop_legacy_signal_backtest.sql` drop hai bảng legacy; `schema.sql` không còn khai báo chúng. Migration cũ vẫn được giữ làm lịch sử, không phải hợp đồng hiện tại.

Áp dụng migration cleanup sẽ xóa vĩnh viễn mọi row legacy. Cần export trước nếu cần audit. Migration không sửa raw, clean hoặc feature data và không cần backfill. Hiện không có signal/backtest executable; hợp đồng mới sẽ được thiết kế trong phase riêng sau khi data và feature được kiểm chứng.

## Verification

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;

select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name in ('stock_daily', 'stock_intraday', 'features')
order by table_name, ordinal_position;
```

Không giả định production đã áp dụng migration mới nhất trước khi chạy verification read-only.
