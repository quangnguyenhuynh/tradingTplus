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
- Ghi: `symbol`, `timeframe`, `time`, `open`, `high`, `low`, `close`, `volume`, `value`, `reference_price`, `ceiling_price`, `floor_price`. `value` là `int(round(close * volume))` tại thời điểm ingest/backfill qua helper `calculate_trade_value`; nếu `close` hoặc `volume` null thì `value` null.
- Upsert theo conflict key: `symbol,timeframe,time`.
- Quy ước hiện tại: chỉ lưu `timeframe = '1m'`. Đây là single source of truth; `5m`, `15m`, `60m`, `1d` được aggregate trong feature engine và không ghi ngược vào `stock_intraday`.

### orderbook_snapshot
- Ghi tối thiểu: `symbol`, `time`, `total_bid_depth_10`, `total_ask_depth_10`.
- Derive thêm trong code: `orderbook_imbalance`, `pressure_score`.
- Upsert theo conflict key: `symbol,time`.

### foreign_trading
- Legacy duplicated daily storage, retained temporarily for compatibility/history.
- Normal daily ingest no longer writes this table; existing rows remain untouched.
- Explicit legacy helpers may still upsert by `symbol,trading_date`; older rows/schema also support `symbol,time` compatibility.

### stock_daily
- Canonical clean daily market data from SSI `DailyStockPrice`.
- Includes `foreign_buy_vol_total`, `foreign_sell_vol_total`, `foreign_buy_val_total`, `foreign_sell_val_total`, `net_foreign_vol`, `net_foreign_val`, and `foreign_current_room`.
- Missing source foreign values remain null.

### features
- Key: `symbol`, `timeframe`, `time`, `last_updated_at`.
- Timeframe đang được tính từ 1m: `1m`, `5m`, `15m`, `60m`, `1d`.
- Price: `open`, `high`, `low`, `close`, `volume`, `value`.
- Return: `return_1m`, `return_5m`, `return_15m`, `return_from_open`, `return_from_prev_close`.
- Trend: `ema9`, `ema20`, `ema50`, `ema9_above_ema20`, `ema20_above_ema50`.
- Momentum: `rsi14`, `macd`, `macd_signal`, `macd_histogram`.
- Volume: `volume_ma20`, `volume_ratio`, `value_ma20`, `value_ratio`.
- Breakout: `high_20_bars`, `low_20_bars`, `close_above_high_20`, `close_below_low_20`.
- VWAP: `vwap_intraday`, `close_above_vwap`, `distance_to_vwap_pct`.
- Candle: `candle_range`, `candle_body`, `candle_body_pct`, `close_position_in_candle`.
- Upsert theo conflict key: `symbol,timeframe,time`.

### trading_signals
- Ghi: `symbol`, `timeframe`, `time`, `signal_type`, `score`, `reason`, `suggestion`, `bucket_time`.
- Upsert theo conflict key: `symbol,timeframe,time,signal_type`.

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

create unique index if not exists trading_signals_symbol_timeframe_time_signal_type_uidx
on public.trading_signals(symbol, timeframe, time, signal_type);

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

## 5) Migration tương ứng trong repo

- File migration mở rộng bảng `features`: `migrations/20260525_expand_features.sql`.

## Complete SSI ingest additions (2026-07-06)

- `securities` stores full SSI `SecuritiesDetails` metadata. The legacy `symbols` table remains for compatibility and init syncs both tables.
- `stock_daily` is the primary daily source for T+ / swing research. It stores the full `DailyStockPrice` payload including OHLC, reference/ceiling/floor, adjusted close, match/deal/traded volume and value, foreign buy/sell/net fields, current room, and trade counts.
- `raw_daily` stores hashed raw `DailyStockPrice` JSON for debugging and backfills.
- `indexes`, `index_components`, and `index_daily` retain SSI index metadata, constituents, and historical `DailyIndex` market context. Their schema/data is preserved, but stock-only daily, EOD, and backfill flows no longer write them; only `sync-master-data`/`init` may update index master tables.
- `stock_intraday` remains the 1m timing source only (`timeframe='1m'`).
- Future feature work should split `daily_features` from `intraday_features`; this ingest task does not add feature calculations.
- `DailyOHLC` is only a secondary cross-check source. `DailyStockPrice` remains the canonical daily source.

## Safe SSI ingest verification and cleanup

- Run `python scripts/check_ssi_ingest_schema.py` after applying migrations to verify required SSI ingest tables/columns through read-only Supabase selects.
- The smoke script `scripts/check_complete_ssi_ingest.py` is read-only by default. `--write` requires an explicit `--date` and refuses weekend/future dates unless `--force` is supplied.
- Accidental smoke-test rows can be removed with the editable SQL helper `sql/cleanup_accidental_ssi_smoke_records.sql`.

## Foreign trading and orderbook ingest additions

- `stock_daily` is the canonical clean daily source and includes foreign buy/sell/net volume/value and end-of-day room fields from `DailyStockPrice`.
- `foreign_trading` is legacy duplicated daily storage. Normal daily ingest no longer writes it, and existing rows remain untouched for compatibility/history.
- `orderbook_snapshot` stores point-in-time 10-level bid/ask snapshots keyed by `(symbol, time)` with total depth, imbalance, pressure score, and raw SSI JSON.
- Run `migrations/20260707_complete_foreign_orderbook_ingest.sql` after the complete SSI ingest schema migration to add missing compatibility columns and indexes if the existing tables are older.

## SSI endpoint source correction

- Public SSI FastConnect Data REST docs list the market endpoints used for this repo: `Securities`, `SecuritiesDetails`, `IndexComponents`, `IndexList`, `DailyOhlc`, `IntradayOhlc`, `DailyIndex`, and `DailyStockPrice`.
- There is no hardcoded public REST `ForeignTrading` endpoint. Normal daily ingest maps foreign fields from `DailyStockPrice` directly into canonical `stock_daily`; only an explicit legacy compatibility helper can still write `foreign_trading`.
- There is no hardcoded public REST orderbook endpoint. `orderbook_snapshot` remains optional and logs unsupported unless an account-specific `SSI_ORDERBOOK_URL` is configured.


## Streaming reconciliation tables

Issue #73 adds/reconciles `stream_raw_snapshot`, `stream_quote_snapshot`, `stream_trade_snapshot`, `stream_foreign_snapshot`, `stream_index_snapshot`, `stream_status_snapshot`, and `stream_bar_snapshot`. Raw rows use a stable `payload_hash` conflict key and keep `received_at` separate from nullable source `time`/`source_time`; clean tables use exact unique indexes matching the application `on_conflict` keys.
# Application-controlled write timestamps

TradingTPlus pipeline writes use timezone-aware Python `Asia/Ho_Chi_Minh` timestamps with an explicit `+07:00` offset rather than
the database server clock as their primary source. `time`/`source_time` remain
market or source-event times and `trading_date` remains the Vietnam trading date.
`created_at` is the first insert time and is preserved on reruns; `updated_at` is
the latest app upsert time; `fetched_at` is raw fetch time; `received_at` is stream
receipt time; and `last_updated_at` is feature calculation/upsert time. Database
`now()` defaults are removed for the scoped pipeline audit columns; writers must send them explicitly.
