from datetime import date

import pytest

from src.pipeline import stock_eod


def _complete(**changes):
    return {
        "symbol_count": 2, "symbols": ["SSI", "HPG"],
        "stock_daily_count": 2, "stock_intraday_count": 200,
        "missing_stock_daily_count": 0, "missing_intraday_count": 0,
        "incomplete_intraday_count": 0, "status": "OK",
    } | changes


def _install(monkeypatch, *, active=("SSI", "HPG"), completeness=None):
    class DB:
        def get_symbols(self): return list(active)
    monkeypatch.setattr(stock_eod, "SupabaseClient", DB)
    calls = []
    monkeypatch.setattr(stock_eod, "daily_run", lambda d, symbols=None: calls.append(("daily", symbols)) or {"symbol_count": len(symbols), "error_count": 0})
    monkeypatch.setattr(stock_eod, "run_intraday_ingest", lambda d, symbols=None: calls.append(("intraday", symbols)) or {"symbol_count": len(symbols), "error_count": 0})
    monkeypatch.setattr(stock_eod, "check_ingest", lambda d, symbols=None: calls.append(("completeness", symbols)) or (completeness or _complete(symbols=symbols, symbol_count=len(symbols))))
    return calls


def test_stock_eod_runs_only_stock_stages_in_order(monkeypatch):
    calls = _install(monkeypatch)
    result = stock_eod.run_stock_eod_pipeline("05/07/2024")
    assert calls == [("daily", ["SSI", "HPG"]), ("intraday", ["SSI", "HPG"]), ("completeness", ["SSI", "HPG"])]
    assert result["flow"] == "stock-eod"
    assert not any("index" in key for key in result)
    assert not hasattr(stock_eod, "run_index_daily_ingest")
    assert not hasattr(stock_eod, "check_index_completeness")


def test_stock_eod_default_date(monkeypatch):
    _install(monkeypatch)
    monkeypatch.setattr(stock_eod, "latest_weekday_on_or_before", lambda: date(2026, 7, 13))
    assert stock_eod.run_stock_eod_pipeline(None)["date"] == "13/07/2026"


def test_stock_eod_normalizes_filters_and_reuses_one_scope(monkeypatch, capsys):
    calls = _install(monkeypatch, active=("SSI", "HPG"))
    result = stock_eod.run_stock_eod_pipeline("10/07/2026", symbols=["ssi", " VNM ", "HPG", "SSI"])
    scope = calls[0][1]
    assert scope == ["SSI", "HPG"]
    assert calls == [("daily", scope), ("intraday", scope), ("completeness", scope)]
    assert calls[0][1] is calls[1][1] is calls[2][1]
    assert result["requested_symbols"] == ["SSI", "VNM", "HPG"]
    assert result["ignored_symbols"] == ["VNM"]
    assert "inactive or unknown" in capsys.readouterr().out


def test_stock_eod_status_depends_only_on_stock_stages(monkeypatch):
    _install(monkeypatch, completeness=_complete(status="PARTIAL", missing_intraday_count=1))
    assert stock_eod.run_stock_eod_pipeline("05/07/2024")["status"] == "PARTIAL"
    _install(monkeypatch, completeness=_complete(status="FAILED", stock_daily_count=0))
    assert stock_eod.run_stock_eod_pipeline("05/07/2024")["status"] == "FAILED"


def test_explicit_scope_with_no_active_symbols_is_not_ingested(monkeypatch):
    calls = _install(monkeypatch, active=("SSI",))
    result = stock_eod.run_stock_eod_pipeline("05/07/2024", symbols=["VNM"])
    assert calls == []
    assert result["ignored_symbols"] == ["VNM"]
    assert result["status"] == "FAILED"
