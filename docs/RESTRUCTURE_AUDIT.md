# SSI v3 restructuring audit

Baseline: 90a57b1; local origin/dev f6e35a5 is its ancestor. Fetch failed because the session proxy was unreachable; latest remote dev was subsequently verified through the GitHub connector to match HEAD (90a57b1b0a2eca80f04fbbe01f36b5d9856d3db5). Worktree was clean. Baseline: 661 passed, 7 skipped; compilation and CLI help passed.

Current: v3 securitiesSummary and indexSummary production adapters coexist with selectable v2 stock daily/intraday. Index preview, combined fetch and master/streaming still use v2. Stock EOD resolves DB scope before source validation. README credentials and several architecture/CLI pages describe superseded v2 behavior.

Plan: remove v2 client/adapter/mapping/authentication and legacy SignalR; disable intraday/master/streaming and composite operations before any I/O. Move modules using RESTRUCTURE_MAPPING.json; split CLI parser/handlers by domain. Preserve v3 request/mapping semantics, raw/clean persistence, independent feature/research formulas and JSON assets. Retire unused engine/data_quality (no callers; obsolete fixed-count/recompute behavior).

Affected paths and planned moves are enumerated in RESTRUCTURE_MAPPING.json. Create provider capability error, CLI handlers, package initializers, bilingual package guides and retirement regression tests. Delete src/ssi/api.py, src/ssi/streaming.py, src/data_sources/ssi_v2.py, v2 mapping and obsolete engine. Replace legacy-dependent fetching/mapping/service and inspector code rather than retaining v2 compatibility.

DB inspection: schema.sql, migrations, database/client.py and persistence boundaries define existing raw/clean/master/feature/research tables and conflict keys. These remain unchanged; no SQL, RPC, schema, migration or data changes; no backfill. Features continue reading stock_daily and historical clean stock_intraday 1m.

Tests: targeted provider/daily/index/feature/research tests first, then full offline regression, compileall, every CLI help path, import/dependency scans and workflow checks. No production writes or live backfills. Live SSI/Supabase checks NOT_RUN without credentials. Rollback: revert the restructuring patch/code deployment; data rollback is unnecessary because this task performs no DB writes.
