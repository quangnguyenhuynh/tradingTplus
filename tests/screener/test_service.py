from src.research.screener import service


def _good():
    return {
        "symbol": "SSI", "time": "2026-08-13T17:00:00+00:00",
        "last_updated_at": "2026-08-14T10:00:00+00:00",
        "close": 110, "ema20": 100, "ema50": 95, "rsi14": 55,
        "macd_histogram": 1, "volume_ratio": 1, "value_ratio": 1,
    }


def test_preview_does_not_write_and_missing_symbol_is_explicit(monkeypatch):
    fake_db = object()
    monkeypatch.setattr(
        service, "resolve_active_symbol_scope",
        lambda db, scope: (["SSI", "HPG"], None, []),
    )
    monkeypatch.setattr(service, "_read_features", lambda db, date: [_good()])
    monkeypatch.setattr(service, "_write_results", lambda *args: 1 / 0)
    result = service.run_stock_screener("14/08/2026", db=fake_db)
    assert result["mode"] == "preview"
    assert result["counts"] == {"PASS": 1, "FAIL": 0, "NOT_EVALUABLE": 1}
    assert result["written"] == 0


def test_apply_writes_exact_result_set(monkeypatch):
    fake_db = object()
    saved = []
    monkeypatch.setattr(
        service, "resolve_active_symbol_scope",
        lambda db, scope: (["SSI"], ["SSI"], []),
    )
    monkeypatch.setattr(service, "_read_features", lambda db, date: [_good()])
    monkeypatch.setattr(service, "_write_results", lambda db, records: saved.extend(records))
    result = service.run_stock_screener("14/08/2026", ["SSI"], apply=True, db=fake_db)
    assert result["written"] == 1
    assert saved[0]["symbol"] == "SSI"
    assert saved[0]["trading_date"] == "2026-08-14"
    assert saved[0]["screener_version"] == "v1"


def test_empty_source_never_writes(monkeypatch):
    saved = []
    monkeypatch.setattr(service, "resolve_active_symbol_scope", lambda db, scope: (["SSI"], None, []))
    monkeypatch.setattr(service, "_read_features", lambda db, date: [])
    monkeypatch.setattr(service, "_write_results", lambda db, records: saved.extend(records))
    result = service.run_stock_screener("14/08/2026", apply=True, db=object())
    assert result["status"] == "FAILED"
    assert result["reason"] == "NO_FEATURE_DATA"
    assert saved == []
