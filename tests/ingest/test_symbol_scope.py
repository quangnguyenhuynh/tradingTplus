import pytest

from src.database.client import SupabaseClient
from src.pipeline.symbol_scope import normalize_symbol_scope, resolve_symbol_scope


def test_normalizes_strips_deduplicates_and_preserves_order():
    assert normalize_symbol_scope(["ssi", " HPG ", "SSI", "fpt"]) == ["SSI", "HPG", "FPT"]


def test_none_means_master_symbols():
    class DB:
        def get_symbols(self):
            return ["ssi", " HPG ", "SSI"]
    assert resolve_symbol_scope(DB(), None) == (["SSI", "HPG"], None)


def test_database_master_scope_reads_only_active_symbols():
    calls = []

    class Query:
        def select(self, columns):
            calls.append(("select", columns)); return self
        def eq(self, column, value):
            calls.append(("eq", column, value)); return self
        def order(self, column):
            calls.append(("order", column)); return self
        def execute(self):
            return type("Result", (), {"data": [{"symbol": "SSI"}]})()

    db = object.__new__(SupabaseClient)
    db.client = type("Client", (), {"table": lambda _self, name: calls.append(("table", name)) or Query()})()
    db._with_retry = lambda fn, **_: fn()

    assert db.get_symbols() == ["SSI"]
    assert ("eq", "status", "active") in calls


@pytest.mark.parametrize("symbols", [[], ["  ", "\t"], [None]])
def test_explicit_empty_scope_is_invalid(symbols):
    with pytest.raises(ValueError, match="at least one"):
        normalize_symbol_scope(symbols)


def test_intraday_scope_requires_both_operator_statuses_and_intersects_request():
    from src.pipeline.symbol_scope import resolve_intraday_symbol_scope

    class DB:
        def get_intraday_symbols(self):
            return ["SSI", "HPG"]

    assert resolve_intraday_symbol_scope(DB(), ["ssi", " VNM ", "HPG", "SSI"]) == (
        ["SSI", "HPG"], ["SSI", "VNM", "HPG"], ["VNM"],
    )


def test_database_intraday_scope_reads_both_active_statuses():
    calls = []
    class Query:
        def select(self, columns): calls.append(("select", columns)); return self
        def eq(self, column, value): calls.append(("eq", column, value)); return self
        def order(self, column): return self
        def execute(self): return type("Result", (), {"data": [{"symbol": "SSI"}]})()
    db = object.__new__(SupabaseClient)
    db.client = type("Client", (), {"table": lambda _self, name: Query()})()
    db._with_retry = lambda fn, **_: fn()
    assert db.get_intraday_symbols() == ["SSI"]
    assert calls.count(("eq", "status", "active")) == 1
    assert calls.count(("eq", "intraday_status", "active")) == 1
