# tradingTplus

Pipeline thu thập dữ liệu SSI -> Supabase, tính feature kỹ thuật theo luồng vận hành rõ ràng; signal/backtest không tự chạy trong Daily/EOD/Intraday phase hiện tại.

## Cấu trúc repo

- `main.py`: CLI entrypoint ngắn cho production flows (`sync-master-data`, `daily`, `intraday-ingest`, `eod`, `features`, `intraday`).
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
python main.py intraday-ingest 20/05/2026 --symbols SSI HPG
python main.py eod 20/05/2026
python main.py features --mode incremental --date 20/05/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m 1d
python main.py intraday --symbols SSI HPG
```

## Scripts hỗ trợ

```bash
python scripts/check_supabase.py
python scripts/check_complete_ssi_ingest.py --symbol SSI
python scripts/check_ssi_ingest_schema.py
python scripts/backfill_sample.py --from-date YYYY-MM-DD --to-date YYYY-MM-DD --symbols SSI FPT
python scripts/fetch_one_day.py --symbol SSI --date 20/05/2026 --dry-run
```

## Ghi chú vận hành

- `daily`, `intraday-ingest`, `eod`, và `intraday` mặc định theo múi giờ VN (UTC+7).
- `daily` chỉ ingest DailyStockPrice/DailyIndex/foreign fields; `intraday-ingest` ingest IntradayOhlc 1m; `eod` orchestrate daily → intraday-ingest → completeness; `features` chạy riêng; `intraday` là legacy feature alias.
- Khi parse timestamp intraday lỗi, hệ thống sẽ bỏ qua candle lỗi thay vì ghi dữ liệu sai thời gian.

## Trạng thái flow hiện tại

- ✅ Production CLI: `init`/`sync-master-data`, `daily`, `intraday-ingest`, `eod`, `features`, `intraday` chạy qua `main.py`; test/debug/manual chạy qua `scripts/`.
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
- `python main.py daily DD/MM/YYYY` writes `raw_daily`, full `stock_daily`, `foreign_trading`, and `index_daily`; `python main.py intraday-ingest DD/MM/YYYY` writes `raw_intraday` and `stock_intraday` (`timeframe='1m'` only).
- `stock_daily` is the canonical daily source for T+ / swing features; `stock_intraday` is only for 1m timing. `DailyOHLC` should be used only for cross-checking.
- The current accepted feature design remains one `features` table keyed by `(symbol, timeframe, time)`; `1d` features come from `stock_daily`, not intraday bars.
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
- `python main.py daily DD/MM/YYYY` ingests stock daily/raw daily, foreign trading, and daily index data only; feature calculation is intentionally disabled in this ingest step.
- `python main.py intraday-ingest DD/MM/YYYY --symbols SSI FPT` ingests SSI IntradayOhlc 1m into raw/clean intraday only.
- `python main.py eod DD/MM/YYYY` runs daily ingest, intraday ingest, and ingest validation; it does not calculate features.
- `python main.py intraday --symbols SSI FPT` is the legacy intraday feature alias and does not ingest SSI candles.
- `python scripts/snapshot_orderbook.py SSI FPT --write` writes an orderbook/bid-ask snapshot manually. If the SSI account/endpoint does not support orderbook data, the pipeline logs `unsupported/missing endpoint` and continues.
- `python scripts/check_ingest.py --date DD/MM/YYYY` prints symbol, securities, stock daily, intraday, index daily, foreign trading, and orderbook snapshot counts plus missing stock-daily symbols.

### SSI API endpoint source note

The hardcoded SSI REST URLs are limited to the endpoints listed in SSI FastConnect Data docs: `AccessToken`, `Securities`, `SecuritiesDetails`, `IndexComponents`, `IndexList`, `DailyOhlc`, `IntradayOhlc`, `DailyIndex`, and `DailyStockPrice`. Foreign trading is derived from `DailyStockPrice` foreign fields; no standalone public `ForeignTrading` REST URL is hardcoded. REST orderbook is not in the public FastConnect Data endpoint list, so `snapshot-orderbook` logs unsupported unless `SSI_ORDERBOOK_URL` is explicitly provided for a private/account-specific endpoint.

### Read-only SSI API inspectors

For raw SSI FastConnect Data REST envelope inspection across the 9 official REST endpoints, use the dedicated read-only inspector:

```bash
python scripts/ssi_api_inspector/inspect.py list
python scripts/ssi_api_inspector/inspect.py run daily-stock-price --symbol SSI --date DD/MM/YYYY --limit 3
python scripts/ssi_api_inspector/inspect.py run all --symbol SSI --date DD/MM/YYYY --index-code VNINDEX --limit 2
```

See `scripts/ssi_api_inspector/README.md` for endpoint coverage, parameters, redaction behavior, and examples. This inspector is the canonical CLI for viewing raw SSI FastConnect Data REST responses; ingest validation and mapper checks remain covered by the dedicated smoke/schema scripts above.

### SSI quote marketdata / orderbook note

SSI FCData docs include bid/ask depth fields in quote marketdata messages, e.g. `BidPrice1`, `BidVol1`, `AskPrice1`, `AskVol1`. That is stream/message payload data, not the same thing as a documented public REST `MarketDepth` endpoint. The orderbook mapper supports those FCData quote fields. Use `scripts/ssi_streaming_inspector/` to inspect raw quote frames and decoded payloads without DB writes.

### SSI SignalR streaming inspector

SSI FCData streaming uses classic ASP.NET SignalR through the production host `https://fc-datahub.ssi.com.vn` and the current client defaults (`v2.0/signalr`, `FcMarketDataV2Hub`, `SwitchChannels`, `Broadcast`). For Phase 0 read-only inspection, use the dedicated streaming inspector:

```bash
python scripts/ssi_streaming_inspector/inspect.py list
python scripts/ssi_streaming_inspector/inspect.py negotiate
python scripts/ssi_streaming_inspector/inspect.py run quote --symbols SSI --timeout 30 --max-messages 3
python scripts/ssi_streaming_inspector/inspect.py run all --symbols SSI --index-codes VNINDEX --timeout 60 --max-messages 2
```

The inspector prints sanitized raw frames, Broadcast wrappers, decoded content, and field coverage against the SSI streaming spec excerpts. It is not a production pipeline, does not write any database, and does not compute derived fields. Operational snapshot scripts remain separate:

```bash
python scripts/snapshot_stream.py --symbols SSI HPG --indexes VNINDEX VN30 --timeout 60 --limit 20 --write
python scripts/snapshot_orderbook.py SSI HPG --timeout 30 --write
```

## CLI production flows (refactored)

Exit code convention: `0` means OK/PARTIAL, `1` means FAILED, and `2` means invalid CLI arguments.

### Production commands

```bash
python main.py sync-master-data
python main.py init
python main.py daily 10/07/2026
python main.py intraday-ingest 10/07/2026 --symbols SSI HPG
python main.py eod 10/07/2026
python main.py features --mode incremental --date 10/07/2026 --symbols SSI HPG --timeframes 1m 5m 15m 60m 1d
python main.py intraday --symbols SSI HPG
```

- `daily` is SSI end-of-day ingest only: `raw_daily`, `stock_daily`, `foreign_trading`, and `index_daily`. It does not ingest intraday candles or calculate features, signals, backtests, or investment decisions.
- `intraday-ingest` is production SSI IntradayOhlc 1m ingest only: `raw_intraday` and `stock_intraday` with `timeframe='1m'`. It may read optional `stock_daily` validation context but does not write daily tables.
- `eod` runs daily ingest, intraday ingest, and ingest completeness validation. It does not calculate features.
- `features` is the explicit feature pipeline. The `1d` feature timeframe is sourced from `stock_daily`, not aggregated from intraday bars.
- `intraday` runs the legacy in-session incremental feature flow for existing `stock_intraday` data; it does not ingest SSI candles.

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

### Phase 0 production flows

* `python main.py daily [DD/MM/YYYY]` ingests raw and clean daily source data only; intraday source data is handled by `intraday-ingest`. It does not calculate features, signals, or backtests.
* `python main.py eod [DD/MM/YYYY]` runs daily ingest, intraday ingest, and ingest completeness validation only. The default EOD date is the latest weekday on or before the run date; actual trading-day validity is determined by SSI data, not by the calendar helper.
* `python main.py features [--mode incremental|full] [--date DD/MM/YYYY] [--symbols SSI HPG] [--timeframes 1m 5m 15m 60m 1d]` is the canonical explicit feature pipeline. Incremental mode with `--date` recalculates only that Vietnam trading date; full mode supports historical reruns/backfills.
* `python main.py intraday` is a legacy compatibility alias for incremental feature calculation on existing `stock_intraday` data. It does not ingest new SSI candles.

Full CLI reference: [`docs/CLI_USAGE.md`](docs/CLI_USAGE.md).

Read-only SQL to inspect potentially suspicious clean daily rows after this change (do not delete automatically):

```sql
select symbol, trading_date, raw
from stock_daily
where raw is not null
  and (
    upper(coalesce(raw->>'Symbol', raw->>'symbol')) is distinct from upper(symbol)
    or coalesce(raw->>'TradingDate', raw->>'tradingDate', raw->>'Date', raw->>'date') is null
  )
order by trading_date desc, symbol;
```


### SSI streaming ingest (Phase 0)

`python main.py streaming-ingest --symbols SSI HPG --indexes VNINDEX VN30 --channels securities-status quote trade foreign-room index realtime-bar --timeout 60 --max-messages-per-channel 1` runs a bounded SSI streaming capture in dry-run/read-only mode. Add `--write` only when database writes are intended. Raw streaming payloads are stored separately from clean snapshot tables; invalid clean rows do not block raw audit storage, and realtime bars are not written to `stock_intraday`.
