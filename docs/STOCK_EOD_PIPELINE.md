# Trạng thái hiện tại / Current capability status

## Exact daily numerics — 4 November 2026

Daily mapping/contract 3.0.0 uses Decimal for money/prices/levels/percentages and
exact integers for discrete quantities. Stock policy 1.1.0 preserves monetary
fractions with FRACTIONAL_MONETARY_VALUE/PARTIAL; Index keeps its separate pipeline
and rejects invalid numerics. Owner must apply **new migration**
`20261104_daily_numeric_precision.sql`; the applied V1 migration is unchanged.
No automatic historical rewrite/backfill/features. Read-only diagnostic:
`python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(use dataset index_daily/identifiers VNINDEX for Index).
[Field matrix, transport, audit, SQL/deployment/rollback and owner commands](DAILY_NUMERIC_PRECISION.md).
This supersedes earlier daily integer-money/float instructions; prior test observations remain historical evidence.


## Stock Daily Data Quality V1 — 3 November 2026

SSI v3 Stock Daily now uses VALID/PARTIAL/REJECTED, field-level NULL quarantine,
immutable RAW and current/history issue evidence. Owner must apply
`20261103_stock_daily_quality_v1.sql` before new writers; historical status stays NULL.
New read-only diagnostic: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Existing `stock-eod`/`stock-eod-backfill` names remain; no automatic backfill/features.
[Policy, deployment, verification SQL and scoped rerun](STOCK_DAILY_QUALITY_V1.md).


Stock Daily EOD vẫn ACTIVE qua SSI v3; chỉ daily ingest và daily completeness.

[CLI hiện tại](CLI_USAGE.md) · [Current state](CURRENT_STATE.md)

## Historical operational record

Các hướng dẫn vận hành cũ bên dưới được giữ làm lịch sử; phần mâu thuẫn với trạng thái trên đã được thay thế. Không chạy lại hướng dẫn v2.

> Historical operational note: SSI v2 REST and legacy SignalR are RETIRED. Intraday/master/streaming ingestion and combined backfill/refill are NOT_IMPLEMENTED. Any older operational instructions below are superseded by [current status](CURRENT_STATE.md). Historical data, formulas and evidence remain unchanged.

# Stock Daily EOD pipeline

`stock-eod` is the daily-only stock source pipeline. The independent workflow now runs at **10:07 UTC (17:07 Asia/Ho_Chi_Minh), Monday–Friday**, or by manual dispatch. Its active workflow is `.github/workflows/stock-eod-scheduled.yml`.

```bash
python main.py stock-eod [DD/MM/YYYY] [--symbols SSI HPG]
```

An omitted date resolves to the latest weekday on or before today in Vietnam; this calendar fallback does not prove an exchange trading session. An omitted symbol list uses `symbols.status='active'`. Explicit symbols are normalized and intersected with that same daily scope; inactive/unknown values are reported in `ignored_symbols`.

The scheduled workflow passes the current Vietnam weekday as an **explicit** `DD/MM/YYYY` target and uses the **most recent elapsed Monday–Friday 17:07 Vietnam slot**, including starts after midnight or on a weekend. The run logs the chosen slot and target. A run delayed past the next scheduled slot may resolve to that newer slot; the previous session then needs an explicit manual rerun. Manual dispatch with an explicit date preserves it; manual dispatch with a blank date deliberately invokes the CLI without a date, retaining its original default behavior. GitHub Actions cannot guarantee an exact start minute; missed slots require an explicitly dated manual rerun.

Stages are: resolve scope, resolved SSI v3 daily source (`securitiesSummary`; retired v2 is unavailable), raw `stock_raw_daily`, validated clean `stock_daily`, then `check_daily_ingest`. The final status uses daily evidence only. The deprecated `intraday_summary` compatibility key is `null`.

The pipeline never calls `IntradayOhlc`, reads/writes intraday or index data, or runs features, signals, backtests, Historical Analog, or automatic backfill.

## Current-run completeness and canonical provenance

Stock EOD completeness reports both canonical presence and rows updated since the run began. A row is current-run complete only when its `updated_at` is current and its `source` matches the resolved provider.

`stock_daily.source` is persistence provenance rather than an SSI market-data contract field. `ssi_v3` means the current canonical row was last successfully written from SSI v3, while `ssi_v2` records historical v2 provenance; that provider is now retired and unavailable. `NULL` is retained for historical rows whose provider cannot be reconstructed safely; it must not be interpreted as v2. A response containing multiple provider records for one symbol/date retains each raw record but writes no ambiguous canonical row.
