"""Explicit Supabase repository for Phase 1 evidence and read-only market inputs."""
from __future__ import annotations

from typing import Any, Callable

from src.pipeline.symbol_scope import normalize_symbol_scope


class Phase1Repository:
    """Singular, testable adapter; no caller depends on plural client methods."""
    def __init__(self, db: Any, page_size: int = 1000):
        self.db, self.client, self.page_size = db, db.client, page_size

    def _execute(self, query, action: str):
        return self.db._with_retry(lambda: query.execute(), action_name=action)

    def _pages(self, table: str, build: Callable[[Any], Any], *, order: tuple[str, ...] = ()) -> list[dict]:
        rows, offset = [], 0
        while True:
            query = build(self.client.table(table).select("*"))
            for column in order:
                query = query.order(column)
            page = list((self._execute(query.range(offset, offset + self.page_size - 1), f"phase1 read {table} offset={offset}").data or []))
            rows.extend(page)
            if len(page) < self.page_size:
                return rows
            offset += self.page_size

    def _one(self, table: str, build) -> dict | None:
        rows = self._pages(table, build)
        return rows[0] if rows else None

    def _upsert(self, table: str, record: dict, conflict: str) -> dict:
        result = self._execute(self.client.table(table).upsert(record, on_conflict=conflict), f"phase1 upsert {table}")
        data = result.data or []
        return dict(data[0]) if data else dict(record)

    def upsert_strategy(self, record): return self._upsert("strategies", record, "strategy_code,version,config_hash")
    def get_strategy(self, code, version, config_hash): return self._one("strategies", lambda q: q.eq("strategy_code", code).eq("version", version).eq("config_hash", config_hash))
    def strategy_status(self, code, version, config_hash):
        row = self.get_strategy(code, version, config_hash)
        return row.get("status") if row else None
    def update_strategy_status(self, code, version, config_hash, status):
        current = self.get_strategy(code, version, config_hash)
        if not current: raise ValueError("exact strategy identity is not registered")
        result = self._execute(self.client.table("strategies").update({"status": status}).eq("strategy_code", code).eq("version", version).eq("config_hash", config_hash), "phase1 strategy status")
        return (result.data or [{**current, "status": status}])[0]
    def upsert_setup(self, record): return self._upsert("strategy_setups", record, "strategy_code,strategy_version,config_hash,symbol,setup_date,target_session")
    def passed_setups(self, target, code, version, config_hash, symbols):
        scope = normalize_symbol_scope(symbols)
        return self._pages("strategy_setups", lambda q: q.eq("target_session", target).eq("strategy_code", code).eq("strategy_version", version).eq("config_hash", config_hash).eq("status", "passed").in_("symbol", scope), order=("symbol",))
    def signal_exists(self, code, version, config_hash, symbol, session): return self._one("signals", lambda q: q.eq("strategy_code", code).eq("strategy_version", version).eq("config_hash", config_hash).eq("symbol", symbol.upper()).eq("signal_session", session)) is not None
    def upsert_signal(self, record): return self._upsert("signals", record, "strategy_code,strategy_version,config_hash,symbol,signal_session")
    def upsert_backtest_run(self, record): return self._upsert("backtest_runs", record, "idempotency_key")
    def get_backtest_run(self, run_id): return self._one("backtest_runs", lambda q: q.eq("id", run_id))
    def upsert_backtest_signal(self, record): return self._upsert("backtest_signals", record, "backtest_run_id,strategy_code,strategy_version,config_hash,symbol,entry_session")
    def upsert_strategy_review(self, record): return self._upsert("strategy_reviews", record, "strategy_code,strategy_version,config_hash,backtest_run_id")
    def get_strategy_review(self, code, version, config_hash, run_id): return self._one("strategy_reviews", lambda q: q.eq("strategy_code", code).eq("strategy_version", version).eq("config_hash", config_hash).eq("backtest_run_id", run_id))
    def features(self, symbols, timeframes, start, end):
        scope = normalize_symbol_scope(symbols)
        return self._pages("features", lambda q: q.in_("symbol", scope).in_("timeframe", timeframes).gte("time", start).lte("time", end), order=("symbol", "timeframe", "time"))
    def intraday(self, symbols, start, end):
        scope = normalize_symbol_scope(symbols)
        return self._pages("stock_intraday", lambda q: q.in_("symbol", scope).eq("timeframe", "1m").gte("time", start).lte("time", end), order=("symbol", "time"))
    def daily(self, symbols, start, end):
        scope = normalize_symbol_scope(symbols)
        return self._pages("stock_daily", lambda q: q.in_("symbol", scope).gte("trading_date", start).lte("trading_date", end), order=("trading_date", "symbol"))
