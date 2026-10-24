# src/ingest/stock_daily

Canonical CLI names and compatible legacy aliases (no removal date): `stock-daily-backfill` → `backfill-daily`. Compatible CLI spellings remain; daily/index behavior is unchanged. Intraday uses the guarded operator range contract. Stock Daily/Index Daily backfill are ACTIVE / WRITE; Stock Intraday backfill is guarded operator-only, DRY_RUN by default, with explicit --write and at most 50 weekday pairs; unattended routes remain disabled.

[Tiếng Việt](README.vi.md)

## Stock Daily ingestion

`daily` is WRITE — raw/clean ingest only. It fetches SSI v3 `securitiesSummary`, retains source payload/hash in `stock_raw_daily`, validates and persists canonical `stock_daily`. It does not run completeness or downstream calculations. No date means the latest weekday strictly before today in Vietnam. Explicit symbols are used directly; omitted symbols load active persisted master symbols.

`stock-eod` and its exact alias `stock-daily` are WRITE — raw/clean ingest plus daily-only completeness. They intersect explicit symbols with active master symbols and report ignored unknown/inactive values. Empty active scope returns FAILED. Their default date is the latest weekday on or before today in Vietnam, unlike `daily`. Completeness checks the current run timing and expected source. Neither route ingests indexes/intraday, writes a separate foreign-trading dataset, or starts features. Deprecated intraday counts/summary do not indicate an intraday operation.

Explicit weekend/future source-write dates are rejected. An empty holiday response is reported; rows are never synthesized. Both SSI and Supabase credentials are required.

```bash
python main.py daily --help
python main.py stock-eod --help
python main.py stock-daily --help
python main.py daily 19/10/2026 --symbols SSI
python main.py daily 19/10/2026 --symbols SSI HPG --data-source ssi_v3
python main.py daily --symbols SSI
python main.py stock-eod --symbols SSI
python main.py stock-daily 19/10/2026 --symbols SSI HPG
```
## Stock Daily historical backfill

WRITE — raw/clean ingest: `stock-daily-backfill` requires `--from` and `--to`; `--from-date` and `--to-date` are aliases. Optional symbols apply to every included date; omitted means active master scope per ingest. Optional `--data-source ssi_v3` makes selection explicit; omission selects the ready v3 adapter, not the literal value `auto`.

The runner skips weekends, rejects future/reversed ranges, records per-day OK/PARTIAL/FAILED and continues across failures. Weekend-only ranges are OK no-ops. It does not verify completeness: inspect daily summaries and perform a separately scoped read-only check. Reruns may update existing clean rows and retain raw evidence. It does not calculate features or call the disabled combined backfill.

```bash
python main.py stock-daily-backfill --help
python main.py stock-daily-backfill --from 01/10/2026 --to 19/10/2026 --symbols SSI HPG --data-source ssi_v3
```

[CLI](../../../docs/CLI_USAGE.md)
