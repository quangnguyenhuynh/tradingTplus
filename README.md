# tradingTplus

Pipeline thu thập dữ liệu SSI -> Supabase, tính feature kỹ thuật theo luồng vận hành rõ ràng; signal/backtest không tự chạy trong Daily/EOD/Intraday phase hiện tại.

## Cấu trúc repo

- `main.py`: CLI entrypoint ngắn cho production flows (`sync-master-data`, `daily`, `eod`, `intraday`).
- `src/ssi/`: client gọi SSI API.
- `src/pipeline/`: orchestration cho Daily ingest, EOD, Intraday, master data và ingest checks.
- `src/database/`: Supabase client + các hàm insert/upsert.
- `src/engine/feature_engine.py`: load dữ liệu 1m, aggregate timeframe và tính indicator/features.
- `src/engine/signal_engine.py`: sinh signal từ features.
- `src/engine/backtest_engine.py`: backtest MVP từ `features` + `trading_signals`.
- `scripts/`: manual/debug/smoke/maintenance tools; các tool có khả năng ghi dữ liệu yêu cầu `--write` rõ ràng khi phù hợp.

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
python main.py sync-master-data
python main.py daily
python main.py daily 20/05/2026
python main.py eod 20/05/2026
python main.py intraday --symbols SSI HPG
```

## Scripts hỗ trợ

```bash
python scripts/check_ssi_api.py
python scripts/check_supabase.py
python scripts/check_symbols.py
python scripts/backfill_sample.py
python scripts/fetch_one_day.py --symbol SSI --date 20/05/2026 --dry-run
```

## Ghi chú vận hành

- `daily`, `eod`, và `intraday` mặc định theo múi giờ VN (UTC+7).
- `daily` chỉ ingest; `eod` ingest + validate + feature; `intraday` xử lý incremental intraday feature.
- Khi parse timestamp intraday lỗi, hệ thống sẽ bỏ qua candle lỗi thay vì ghi dữ liệu sai thời gian.

## Trạng thái flow hiện tại

- ✅ Production CLI: `init`/`sync-master-data`, `daily`, `eod`, `intraday` chạy qua `main.py`; test/debug/manual chạy qua `scripts/`.
- ✅ Feature: có engine tính indicator cho `1m`, `5m`, `15m`, `60m`, `1d` và lưu vào bảng `features`.
- ✅ Timeframe: `stock_intraday` chỉ lưu 1m; các timeframe cao hơn được aggregate trong bộ nhớ từ 1m trước khi tính feature.
- ✅ Signal: có engine sinh tín hiệu rule-based và lưu `trading_signals`.
- ✅ Backtest: có MVP tính PnL, winrate, max drawdown và Sharpe đơn giản từ `features` + `trading_signals`.

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
- Backtest MVP đã được bổ sung trong `src/engine/backtest_engine.py`; có thể gọi `run_backtest_engine(target_date)` hoặc test bằng dữ liệu in-memory qua `run_backtest(...)`.

### Complete SSI ingest layer

The ingest layer now persists SSI daily fundamentals before signal/backtest work:

- `python main.py init` keeps syncing legacy `symbols` and also fills full `securities` metadata from `SecuritiesDetails`.
- `python main.py daily DD/MM/YYYY` writes `raw_daily`, full `stock_daily`, `raw_intraday`, `stock_intraday` (`timeframe='1m'` only), and `index_daily`.
- `stock_daily` is the canonical daily source for T+ / swing features; `stock_intraday` is only for 1m timing. `DailyOHLC` should be used only for cross-checking.
- Later feature work should split `daily_features` and `intraday_features` instead of deriving 1d technical features from intraday bars.
- Smoke check without DB writes: `python scripts/check_complete_ssi_ingest.py --symbol SSI --date DD/MM/YYYY`.

### Safe SSI smoke/backfill workflow

Use this guarded flow before any real SSI backfill:

1. Apply migrations in Supabase SQL Editor, including `migrations/20260706_complete_ssi_ingest_schema.sql`.
2. Verify the applied schema without writes:
   ```bash
   python scripts/check_ssi_ingest_schema.py
   ```
3. Run the complete SSI ingest smoke test in read-only mode. If `--date` is omitted, it uses the latest previous weekday and prints that choice clearly:
   ```bash
   python scripts/check_complete_ssi_ingest.py --symbol SSI
   ```
4. Run a write smoke test only with an explicit date. `--write` refuses weekend/future dates unless `--force` is passed and writes `raw_daily`, `stock_daily`, `securities`, `indexes`, and `index_daily` by default:
   ```bash
   python scripts/check_complete_ssi_ingest.py --symbol SSI --date DD/MM/YYYY --write
   ```
5. Only write intraday smoke-test rows when explicitly requested:
   ```bash
   python scripts/check_complete_ssi_ingest.py --symbol SSI --date DD/MM/YYYY --write --write-intraday
   ```
6. Run real backfills only after the smoke checks pass. The sample runner has no hardcoded defaults and requires explicit symbols/date range:
   ```bash
   python scripts/backfill_sample.py
python scripts/fetch_one_day.py --symbol SSI --date 20/05/2026 --dry-run --from-date YYYY-MM-DD --to-date YYYY-MM-DD --symbols SSI FPT
   ```

If an accidental smoke-test write must be removed, edit and run `sql/cleanup_accidental_ssi_smoke_records.sql` for the exact symbol/date.

### SSI ingest CLI additions

- `python main.py sync-master-data` (alias of `init`) syncs symbols, securities, indexes, and index components.
- `python main.py daily DD/MM/YYYY` ingests stock daily/raw daily, 1m intraday, foreign trading, and daily index data only; feature calculation is intentionally disabled in this ingest step.
- `python main.py eod DD/MM/YYYY` runs daily ingest, ingest validation, and feature calculation for `1m`, `5m`, `15m`, `60m`, and `1d`.
- `python main.py intraday --symbols SSI FPT` runs the intraday incremental feature flow without daily ingest.
- `python scripts/snapshot_orderbook.py SSI FPT --write` writes an orderbook/bid-ask snapshot manually. If the SSI account/endpoint does not support orderbook data, the pipeline logs `unsupported/missing endpoint` and continues.
- `python scripts/check_ingest.py --date DD/MM/YYYY` prints symbol, securities, stock daily, intraday, index daily, foreign trading, and orderbook snapshot counts plus missing stock-daily symbols.

### SSI API endpoint source note

The hardcoded SSI REST URLs are limited to the endpoints listed in SSI FastConnect Data docs: `AccessToken`, `Securities`, `SecuritiesDetails`, `IndexComponents`, `IndexList`, `DailyOhlc`, `IntradayOhlc`, `DailyIndex`, and `DailyStockPrice`. Foreign trading is derived from `DailyStockPrice` foreign fields; no standalone public `ForeignTrading` REST URL is hardcoded. REST orderbook is not in the public FastConnect Data endpoint list, so `snapshot-orderbook` logs unsupported unless `SSI_ORDERBOOK_URL` is explicitly provided for a private/account-specific endpoint.

### Read-only SSI API inspector

To inspect what each SSI API call returns and how the ingest mapper will shape it before any DB write, run:

```bash
python scripts/inspect_ssi_ingest_api.py --symbol SSI --date DD/MM/YYYY --index-code VNINDEX
```

The script prints raw and mapped samples for symbols, securities details, DailyStockPrice (`raw_daily`/`stock_daily`), IntradayOhlc (`raw_intraday`/`stock_intraday` 1m), foreign trading derived from DailyStockPrice, IndexList (`indexes`), DailyIndex (`index_daily`), IndexComponents, and optional orderbook. It is read-only and never writes to Supabase.


### SSI quote marketdata / orderbook note

SSI FCData docs include bid/ask depth fields in quote marketdata messages, e.g. `BidPrice1`, `BidVol1`, `AskPrice1`, `AskVol1`. That is stream/message payload data, not the same thing as a documented public REST `MarketDepth` endpoint. The orderbook mapper supports those FCData quote fields. To verify a captured quote payload without DB writes:

```bash
python scripts/inspect_ssi_quote_payload.py --file quote_payload.json
# or
echo '{"Symbol":"SSI","BidPrice1":25000,"BidVol1":1000,"AskPrice1":25100,"AskVol1":900}' | python scripts/inspect_ssi_quote_payload.py
```

### SSI SignalR streaming

SSI FCData streaming uses SignalR, not a raw websocket endpoint such as `wss://fc-datahub.ssi.com.vn/v2.0`.

Default config:

```env
SSI_STREAMING_ENABLED=true
SSI_STREAMING_BASE_URL=https://fc-datahub.ssi.com.vn/
SSI_SIGNALR_PATH=v2.0/signalr
SSI_SIGNALR_HUB=FcMarketDataV2Hub
SSI_SIGNALR_RECEIVE_METHOD=Broadcast
SSI_SIGNALR_SWITCH_METHOD=SwitchChannels
ORDERBOOK_SNAPSHOT_TIMEOUT_SEC=20
```

Test streaming quotes:

```bash
python scripts/test_ssi_streaming.py SSI --timeout 30 --raw
python scripts/test_ssi_streaming.py SSI --timeout 30 --write
python scripts/test_ssi_streaming.py SSI HPG FPT --timeout 30 --raw
python scripts/test_ssi_streaming_parser.py
```

Snapshot orderbook via SignalR:

```bash
python scripts/snapshot_orderbook.py SSI --write
python scripts/snapshot_orderbook.py --debug --timeout 30 SSI --write
```

### Debug SignalR negotiate

To inspect raw SSI SignalR negotiate responses without `signalrcore`, websocket, Supabase, or DB writes:

```bash
python scripts/debug_signalr_negotiate.py
python scripts/debug_signalr_negotiate.py --method GET
python scripts/debug_signalr_negotiate.py --no-auth
```

The script prints the SignalR URL, each negotiate URL variant, request method/headers, status code, response headers, first 2000 response chars, parsed JSON if available, and warnings for non-integer `negotiateVersion` values.

### SSI ASP.NET SignalR classic note

SSI FCData negotiate returns `ProtocolVersion`/`ConnectionToken` (classic ASP.NET SignalR), not ASP.NET Core `negotiateVersion`. The streaming client therefore uses `requests` + `websocket-client` and does not use `signalrcore`.

Classic SignalR test command:

```bash
python scripts/test_ssi_signalr2_streaming.py SSI --timeout 60 --raw
python scripts/test_ssi_signalr2_streaming.py SSI --timeout 60 --write
```

## CLI production flows (refactored)

Exit code convention: `0` means OK/PARTIAL, `1` means FAILED, and `2` means invalid CLI arguments.

### Production commands

```bash
python main.py sync-master-data
python main.py init
python main.py daily 10/07/2026
python main.py eod 10/07/2026
python main.py intraday --symbols SSI HPG
```

- `daily` is SSI end-of-day ingest only: `raw_daily`, `stock_daily`, daily `raw_intraday` 1m, `stock_intraday` 1m, `foreign_trading`, and `index_daily`. It does not calculate features, signals, backtests, or investment decisions.
- `eod` runs daily ingest, ingest validation, and incremental feature calculation for `1m`, `5m`, `15m`, `60m`, and `1d`. The `1d` feature timeframe is sourced from `stock_daily`, not aggregated from intraday bars. Signal and backtest steps are placeholders for a later phase.
- `intraday` runs the in-session incremental feature flow for existing `stock_intraday` data. It supports all symbols by default or a focused subset via `--symbols`; signal, backtest-stat lookup, and alerting are placeholders for a later phase.

### Manual and maintenance commands

```bash
python scripts/run_features.py --mode incremental --symbols SSI HPG --timeframes 1m 5m 15m 1d
python scripts/check_ingest.py --date 10/07/2026
python scripts/eod_dry_run.py --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 1d --json
python scripts/fetch_one_day.py --symbol SSI --date 10/07/2026 --dry-run
python scripts/fetch_one_day.py --symbol SSI --date 10/07/2026 --write
python scripts/snapshot_orderbook.py SSI HPG --timeout 30 --debug --write
python scripts/snapshot_stream.py --symbols SSI HPG --indexes VNINDEX VN30 --timeout 60 --limit 20 --write
```

Manual/debug/smoke tools live in `scripts/` and use `argparse` with a `main()` guard. Scripts that can write data default to read-only/dry-run unless `--write` is explicitly supplied.
