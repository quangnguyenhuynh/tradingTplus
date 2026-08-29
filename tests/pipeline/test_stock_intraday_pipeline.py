from datetime import date
from src.pipeline import stock_intraday


def _install(monkeypatch, active=("SSI", "HPG"), completeness_status="OK", ingest_status="OK"):
    calls = []
    class DB:
        def get_intraday_symbols(self): return list(active)
    monkeypatch.setattr(stock_intraday, "SupabaseClient", DB)
    monkeypatch.setattr(stock_intraday, "run_intraday_ingest", lambda d, symbols=None: calls.append(("intraday", symbols)) or {"status": ingest_status, "symbol_count": len(symbols), "error_count": 0})
    monkeypatch.setattr(stock_intraday, "check_intraday_ingest", lambda d, symbols=None: calls.append(("completeness", symbols)) or {"status": completeness_status, "stock_intraday_count": len(symbols), "missing_intraday_count": 0})
    return calls


def test_intraday_only_stages_reuse_effective_scope(monkeypatch):
    calls = _install(monkeypatch)
    result = stock_intraday.run_stock_intraday_pipeline("10/07/2026", symbols=["ssi", "VNM", "HPG"])
    assert calls == [("intraday", ["SSI", "HPG"]), ("completeness", ["SSI", "HPG"])]
    assert calls[0][1] is calls[1][1]
    assert result["ignored_symbols"] == ["VNM"] and result["status"] == "OK"
    assert not hasattr(stock_intraday, "daily_run")


def test_intraday_no_effective_symbol_fails_without_ssi(monkeypatch):
    calls = _install(monkeypatch, active=("SSI",))
    result = stock_intraday.run_stock_intraday_pipeline("10/07/2026", symbols=["VNM"])
    assert calls == [] and result["status"] == "FAILED"


def test_intraday_default_date_is_weekday_on_or_before(monkeypatch):
    _install(monkeypatch)
    monkeypatch.setattr(stock_intraday, "latest_weekday_on_or_before", lambda: date(2026, 7, 13))
    assert stock_intraday.run_stock_intraday_pipeline(None)["date"] == "13/07/2026"


def test_missing_daily_context_stays_observable(monkeypatch):
    _install(monkeypatch, ingest_status="PARTIAL")
    result = stock_intraday.run_stock_intraday_pipeline("10/07/2026")
    assert result["status"] == "PARTIAL"
    assert "intraday ingest is partial" in result["warnings"]
