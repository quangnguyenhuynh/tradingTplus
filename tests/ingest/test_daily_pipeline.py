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
    stock_calls = []
    monkeypatch.setattr(daily, "fetch_daily_for_symbol_with_clients", lambda ssi, db_arg, symbol, date: stock_calls.append(symbol) or {"status": "OK", "daily_rows": 1})
    return stock_calls


def test_explicit_scope_only_ingests_requested_stocks(monkeypatch):
    db = DB()
    stock_calls = _setup(monkeypatch, db)
    summary = daily.run_daily_ingest("10/07/2026", symbols=["ssi", " HPG ", "SSI"])
    assert stock_calls == ["SSI", "HPG"]
    assert db.get_symbols_calls == 0
    assert summary["symbol_scope"] == "EXPLICIT"
    assert summary["requested_symbols"] == ["SSI", "HPG"]
    assert summary["symbols"] == ["SSI", "HPG"]
    assert summary["symbol_count"] == 2


def test_omitted_scope_uses_master_symbols(monkeypatch):
    db = DB()
    stock_calls = _setup(monkeypatch, db)
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


def test_daily_uses_only_daily_ssi_endpoints_and_preserves_summary(monkeypatch):
    class FailFastSSI:
        def __init__(self):
            self.stock_calls = []
            self.index_calls = []

        def get_daily_price(self, symbol, date):
            self.stock_calls.append((symbol, date))
            return {"Symbol": symbol}

        def get_daily_index(self, index_code, date):
            raise AssertionError("daily called DailyIndex")

        def _forbidden(self, *args, **kwargs):
            raise AssertionError("daily called a master-data SSI endpoint")

        get_index_list = _forbidden
        get_index_components = _forbidden
        get_intraday = _forbidden
        get_symbols = _forbidden
        get_security_details = _forbidden

    db = DB()
    ssi = FailFastSSI()
    monkeypatch.setattr(daily, "SupabaseClient", lambda: db)
    monkeypatch.setattr(daily, "SSIApi", lambda: ssi)
    monkeypatch.setattr(
        daily,
        "fetch_daily_for_symbol_with_clients",
        lambda client, db_arg, symbol, date: (
            client.get_daily_price(symbol, date) and {"status": "OK", "daily_rows": 1}
        ),
    )
    summary = daily.run_daily_ingest("10/07/2026")

    assert ssi.stock_calls == [
        ("SSI", "10/07/2026"),
        ("HPG", "10/07/2026"),
        ("FPT", "10/07/2026"),
    ]
    assert ssi.index_calls == []
    assert summary["index_daily_count"] == 0
    assert {
        "daily_valid_count", "total_daily_rows", "total_candles", "total_foreign",
        "index_daily_count", "error_count", "error_type_counts", "errors", "status",
    } <= summary.keys()


def test_daily_never_exposes_index_persistence_dependencies(monkeypatch):
    class FailFastDB(DB):
        def __getattr__(self, name):
            if name in {"upsert_index_daily", "upsert_indexes", "upsert_index_components"}:
                raise AssertionError(f"daily accessed forbidden DB method {name}")
            raise AttributeError(name)

    db = FailFastDB()
    stock_calls = _setup(monkeypatch, db)
    summary = daily.run_daily_ingest("10/07/2026", symbols=["SSI"])
    assert stock_calls == ["SSI"]
    assert summary["status"] == "OK"
