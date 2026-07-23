import pytest

from src.pipeline import daily


class DB:
    def __init__(self):
        self.get_symbols_calls = 0
    def get_symbols(self):
        self.get_symbols_calls += 1
        return ["SSI", "HPG", "FPT"]


def _setup(monkeypatch, db):
    monkeypatch.setattr(daily, "SupabaseClient", lambda: db)
    monkeypatch.setattr(daily, "SSIApi", lambda: object())
    index_calls = []
    monkeypatch.setattr(daily, "sync_indexes", lambda **kwargs: index_calls.append("indexes"))
    monkeypatch.setattr(daily, "sync_index_components", lambda *args, **kwargs: index_calls.append("components"))
    monkeypatch.setattr(daily, "fetch_daily_indexes", lambda *args, **kwargs: index_calls.append("daily") or 2)
    stock_calls = []
    monkeypatch.setattr(daily, "fetch_daily_for_symbol_with_clients", lambda ssi, db_arg, symbol, date: stock_calls.append(symbol) or {"status": "OK", "daily_rows": 1})
    return stock_calls, index_calls


def test_explicit_scope_only_ingests_requested_stocks_and_keeps_index_work(monkeypatch):
    db = DB()
    stock_calls, index_calls = _setup(monkeypatch, db)
    summary = daily.run_daily_ingest("10/07/2026", symbols=["ssi", " HPG ", "SSI"])
    assert stock_calls == ["SSI", "HPG"]
    assert db.get_symbols_calls == 0
    assert index_calls == ["indexes", "components", "daily"]
    assert summary["symbol_scope"] == "EXPLICIT"
    assert summary["requested_symbols"] == ["SSI", "HPG"]
    assert summary["symbols"] == ["SSI", "HPG"]
    assert summary["symbol_count"] == 2


def test_omitted_scope_uses_master_symbols(monkeypatch):
    db = DB()
    stock_calls, _ = _setup(monkeypatch, db)
    summary = daily.run_daily_ingest("10/07/2026")
    assert stock_calls == ["SSI", "HPG", "FPT"]
    assert db.get_symbols_calls == 1
    assert summary["symbol_scope"] == "ALL_ACTIVE"
    assert summary["requested_symbols"] is None


def test_explicit_empty_scope_fails_before_master_fallback(monkeypatch):
    db = DB()
    monkeypatch.setattr(daily, "SupabaseClient", lambda: db)
    with pytest.raises(ValueError):
        daily.run_daily_ingest("10/07/2026", symbols=[])
    assert db.get_symbols_calls == 0
