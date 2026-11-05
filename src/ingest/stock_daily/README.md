# src/ingest/stock_daily

## EOD backfill ownership — 5 November 2026

| Responsibility | Canonical module |
| --- | --- |
| Stock runner + `_run_ingest_backfill` | `src/ingest/stock_daily/backfill.py` |
| Index runner | `src/ingest/index_daily/index_backfill.py` |
| Five shared range/report helpers | `src/ingest/shared/backfill_range.py` |
| Guarded Intraday and legacy compatibility | `src/ingest/maintenance/backfill.py` |

Stock/Index consume shared helpers directly. Maintenance re-exports the Stock
runner and old helper names without copying logic. Public `src.ingest` import
names remain; the Stock lazy export now points to its domain. CLI handlers keep
using the same public exports. No CLI/options/JSON flow, algorithm, policy,
persistence or guard change. This refactor needs no migration or data backfill.

[Move, compatibility and verification report](../../../docs/backfill/README.md).


## Exact daily numerics — 4 November 2026

Daily mapping/contract 3.0.0 uses Decimal for money/prices/levels/percentages and
exact integers for discrete quantities. Stock policy 1.1.0 preserves monetary
fractions with FRACTIONAL_MONETARY_VALUE/PARTIAL; Index keeps its separate pipeline
and rejects invalid numerics. Owner must apply **new migration**
`20261104_daily_numeric_precision.sql`; the applied V1 migration is unchanged.
No automatic historical rewrite/backfill/features. Read-only diagnostic:
`python main.py daily-numeric-quality --dataset stock_daily --identifiers TCB --date 12/03/2025`
(use dataset index_daily/identifiers VNINDEX for Index).
[Field matrix, transport, audit, SQL/deployment/rollback and owner commands](../../../docs/DAILY_NUMERIC_PRECISION.md).
This supersedes earlier daily integer-money/float instructions; prior test observations remain historical evidence.


## Stock Daily Data Quality V1 — 3 November 2026

SSI v3 Stock Daily now uses VALID/PARTIAL/REJECTED, field-level NULL quarantine,
immutable RAW and current/history issue evidence. Owner must apply
`20261103_stock_daily_quality_v1.sql` before new writers; historical status stays NULL.
New read-only diagnostic: `python main.py stock-eod-quality --symbols TCB --from 05/03/2026 --to 06/03/2026 --raw-clean-missing`.
Existing `stock-eod`/`stock-eod-backfill` names remain; no automatic backfill/features.
[Policy, deployment, verification SQL and scoped rerun](../../../docs/STOCK_DAILY_QUALITY_V1.md).


## Canonical EOD CLI — 28 October 2026

| Command | Existing behavior retained |
| --- | --- |
| `stock-eod` | Stock ingest + existing daily completeness; active-symbol filtering |
| `stock-eod-backfill` | Inclusive stock daily backfill; no added completeness |
| `index-eod` | Existing index daily raw/clean ingest |
| `index-eod-backfill` | Existing inclusive index daily backfill |

Only these four top-level names are supported for stock/index EOD ingest/backfill.
Removed (no aliases/redirects): `daily`, `stock-daily`, `stock-daily-backfill`,
`backfill-daily`, `index-daily`, `index-daily-backfill`, `index-backfill`.
Old direct daily had different date/scope/completeness semantics and is retired;
stock-eod retains run_stock_eod_pipeline rather than adopting daily_run behavior.
Stock/index EOD defaults resolve the latest weekday on/before today in Vietnam;
original date validation, scope rules, summaries and exit codes remain unchanged.
Backfill date aliases --from/--from-date and --to/--to-date remain available.
PARTIAL can still exit 0 under existing _status_to_exit; no exit-policy changes.
Internal daily_run/run_daily_ingest/run_index_daily_ingest/backfill imports,
stock_daily/index_daily dataset IDs and JSON flows (including index-daily,
backfill-daily/index-backfill) remain unchanged. Inspector `stock-daily` remains.
Stock/index pipelines stay separate; no automatic feature/signal/backtest.
The October CLI naming change required no migration; V1 requirements are above. Do not execute WRITE
examples to verify naming. Historical naming/alias reports below are superseded.

```bash
python main.py stock-eod --help
python main.py stock-eod-backfill --help
python main.py index-eod --help
python main.py index-eod-backfill --help
```


Canonical EOD backfills: `stock-eod-backfill`, `index-eod-backfill`; old EOD aliases are removed. Intraday alone retains `stock-intraday-backfill` / `backfill-intraday`. Existing runner behavior is unchanged.

[Tiếng Việt](README.vi.md)

## Stock Daily ingestion

**Historical / đã nghỉ:** `daily` is WRITE — raw/clean ingest only. It fetches SSI v3 `securitiesSummary`, retains source payload/hash in `stock_raw_daily`, validates and persists canonical `stock_daily`. It does not run completeness or downstream calculations. No date means the latest weekday strictly before today in Vietnam. Explicit symbols are used directly; omitted symbols load active persisted master symbols. Removed top-level command; use stock-eod with its existing active scope and completeness.

`stock-eod` is WRITE — raw/clean ingest plus daily-only completeness. They intersect explicit symbols with active master symbols and report ignored unknown/inactive values. Empty active scope returns FAILED. Their default date is the latest weekday on or before today in Vietnam, unlike `daily`. Completeness checks the current run timing and expected source. Neither route ingests indexes/intraday, writes a separate foreign-trading dataset, or starts features. Deprecated intraday counts/summary do not indicate an intraday operation.

Explicit weekend/future source-write dates are rejected. An empty holiday response is reported; rows are never synthesized. Both SSI and Supabase credentials are required.

```bash
python main.py stock-eod --help
python main.py stock-eod --help
python main.py stock-eod --help
python main.py stock-eod 19/10/2026 --symbols SSI
python main.py stock-eod 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py stock-eod --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-eod 19/10/2026 --symbols SSI HPG
```
## Stock Daily historical backfill

WRITE — raw/clean ingest: `stock-eod-backfill` requires `--from` and `--to`; `--from-date` and `--to-date` are aliases. Optional symbols apply to every included date; omitted means active master scope per ingest. Optional `--data-source ssi_v3` makes selection explicit; omission selects the ready v3 adapter, not the literal value `auto`.

The runner skips weekends, rejects future/reversed ranges, records per-day OK/PARTIAL/FAILED and continues across failures. Weekend-only ranges are OK no-ops. It does not verify completeness: inspect daily summaries and perform a separately scoped read-only check. Reruns may update existing clean rows and retain raw evidence. It does not calculate features or call the disabled combined backfill.

```bash
python main.py stock-eod-backfill --help
python main.py stock-eod-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```

[CLI](../../../docs/CLI_USAGE.md)
