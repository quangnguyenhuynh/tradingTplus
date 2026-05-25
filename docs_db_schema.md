# DB Schema Overview (from code usage)

Tài liệu này tổng hợp schema Supabase mà code hiện tại đang **đọc/ghi**.

## 1) Danh sách bảng đang dùng

- `symbols`
- `raw_intraday`
- `stock_intraday`
- `orderbook_snapshot`
- `foreign_trading`
- `features`
- `trading_signals`
- `backtest_data`

Nguồn suy luận: các lệnh `table('...')` trong `src/database/client.py`, `src/engine/feature_engine.py`, `src/engine/signal_engine.py`, `scripts/check_supabase.py`.

## 2) Cột tối thiểu theo từng bảng

### symbols
- Ghi/đọc: `symbol`, `market`, `name`.
- Dùng để load danh sách mã cho pipeline.

### raw_intraday
- Ghi: `symbol`, `time`, `open`, `high`, `low`, `close`, `volume`, `data_hash`.
- Upsert mong muốn theo conflict key: `symbol,time,data_hash`.

### stock_intraday
- Ghi: `symbol`, `timeframe`, `time`, `open`, `high`, `low`, `close`, `volume`, `value`, `volume_delta`, `reference_price`, `ceiling_price`, `floor_price`.
- Upsert theo conflict key: `symbol,timeframe,time`.

### orderbook_snapshot
- Ghi tối thiểu: `symbol`, `time`, `total_bid_depth_10`, `total_ask_depth_10`.
- Derive thêm trong code: `orderbook_imbalance`, `pressure_score`.
- Upsert theo conflict key: `symbol,time`.

### foreign_trading
- Ghi tối thiểu: `symbol`, `time`, `buy_vol`, `sell_vol`.
- Derive thêm trong code: `net_vol`.
- Upsert theo conflict key: `symbol,time`.

### features
- Ghi: `symbol`, `timeframe`, `time`, `close`, `rsi`, `macd`, `atr`, `volume_spike`, `ema_20`, `ema_50`, `vwap`, `bb_upper`, `bb_lower`, `last_updated_at`.
- Upsert theo conflict key: `symbol,timeframe,time`.

### trading_signals
- Ghi: `symbol`, `timeframe`, `time`, `signal_type`, `score`, `reason`, `suggestion`, `bucket_time`.
- Upsert theo conflict key: `symbol,signal_type,bucket_time`.

### backtest_data
- Chưa có engine backtest chính thức, nhưng client hỗ trợ upsert theo: `symbol,timeframe,time`.

## 3) Constraint/index khuyến nghị

Các conflict key bên dưới nên có **UNIQUE INDEX** tương ứng:

```sql
create unique index if not exists symbols_symbol_uidx
on public.symbols(symbol);

create unique index if not exists raw_intraday_symbol_time_data_hash_uidx
on public.raw_intraday(symbol, time, data_hash);

create unique index if not exists stock_intraday_symbol_timeframe_time_uidx
on public.stock_intraday(symbol, timeframe, time);

create unique index if not exists orderbook_snapshot_symbol_time_uidx
on public.orderbook_snapshot(symbol, time);

create unique index if not exists foreign_trading_symbol_time_uidx
on public.foreign_trading(symbol, time);

create unique index if not exists features_symbol_timeframe_time_uidx
on public.features(symbol, timeframe, time);

create unique index if not exists trading_signals_symbol_signal_type_bucket_time_uidx
on public.trading_signals(symbol, signal_type, bucket_time);

create unique index if not exists backtest_data_symbol_timeframe_time_uidx
on public.backtest_data(symbol, timeframe, time);
```

## 4) SQL kiểm tra nhanh schema hiện tại

```sql
-- Danh sách bảng public
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;

-- Cột của từng bảng
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name in (
    'symbols','raw_intraday','stock_intraday','orderbook_snapshot',
    'foreign_trading','features','trading_signals','backtest_data'
  )
order by table_name, ordinal_position;

-- Index hiện có
select tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and tablename in (
    'symbols','raw_intraday','stock_intraday','orderbook_snapshot',
    'foreign_trading','features','trading_signals','backtest_data'
  )
order by tablename, indexname;
```
