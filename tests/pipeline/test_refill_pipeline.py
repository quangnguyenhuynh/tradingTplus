import pytest

from src.pipeline import refill


def _source(status="OK", processed_days=1):
    return {
        "flow": "backfill",
        "status": status,
        "processed_days": processed_days,
        "skipped_weekend_days": 0 if processed_days else 2,
        "day_summaries": [],
        "errors": [],
    }


def _feature(flow, status="OK"):
    return {"flow": flow, "status": status, "total_records": 2, "errors": []}


def test_refill_calls_exact_scope_and_stages_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda start, end, symbols=None: calls.append(("source", start, end, symbols)) or _source())
    monkeypatch.setattr(refill, "run_daily_feature_backfill", lambda start, end, symbols=None: calls.append(("daily", start, end, symbols)) or _feature("features-daily-backfill"))
    monkeypatch.setattr(refill, "run_intraday_feature_backfill", lambda start, end, symbols=None, timeframes=None: calls.append(("intraday", start, end, symbols, timeframes)) or _feature("features-intraday-backfill"))

    result = refill.run_refill_pipeline("01/07/2026", "02/07/2026", " ssi ")

    assert calls == [
        ("source", "01/07/2026", "02/07/2026", ["SSI"]),
        ("daily", "01/07/2026", "02/07/2026", ["SSI"]),
        ("intraday", "01/07/2026", "02/07/2026", ["SSI"], ("15m", "60m")),
    ]
    assert result["status"] == "OK"
    assert result["symbol"] == "SSI"
    assert set(result["stages"]) == {"source_backfill", "features_daily", "features_intraday"}


@pytest.mark.parametrize("symbol", ["", "   ", "ALL", "ssi hpg", "SSI,HPG"])
def test_refill_rejects_non_single_symbol_before_any_stage(monkeypatch, symbol):
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda *_a, **_k: pytest.fail("source called"))
    with pytest.raises(ValueError, match="symbol"):
        refill.run_refill_pipeline("01/07/2026", "02/07/2026", symbol)


def test_source_partial_runs_features_and_cannot_become_ok(monkeypatch):
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda *_a, **_k: _source("PARTIAL"))
    monkeypatch.setattr(refill, "run_daily_feature_backfill", lambda *_a, **_k: _feature("features-daily-backfill"))
    monkeypatch.setattr(refill, "run_intraday_feature_backfill", lambda *_a, **_k: _feature("features-intraday-backfill"))
    assert refill.run_refill_pipeline("01/07/2026", "02/07/2026", "SSI")["status"] == "PARTIAL"


def test_source_failed_skips_both_features(monkeypatch):
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda *_a, **_k: _source("FAILED"))
    monkeypatch.setattr(refill, "run_daily_feature_backfill", lambda *_a, **_k: pytest.fail("daily called"))
    monkeypatch.setattr(refill, "run_intraday_feature_backfill", lambda *_a, **_k: pytest.fail("intraday called"))
    result = refill.run_refill_pipeline("01/07/2026", "02/07/2026", "SSI")
    assert result["status"] == "FAILED"
    assert result["stages"]["features_daily"]["status"] == "SKIPPED"
    assert result["stages"]["features_intraday"]["status"] == "SKIPPED"


def test_feature_exception_does_not_stop_other_branch_and_has_context(monkeypatch):
    calls = []
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda *_a, **_k: _source())
    monkeypatch.setattr(refill, "run_daily_feature_backfill", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("db\nfailed")))
    monkeypatch.setattr(refill, "run_intraday_feature_backfill", lambda *_a, **_k: calls.append("intraday") or _feature("features-intraday-backfill"))
    result = refill.run_refill_pipeline("01/07/2026", "02/07/2026", "SSI")
    assert calls == ["intraday"]
    assert result["status"] == "PARTIAL"
    assert result["errors"] == [{
        "stage": "features_daily", "symbol": "SSI", "from_date": "01/07/2026",
        "to_date": "02/07/2026", "error": "db failed",
    }]


def test_both_feature_failures_make_final_failed(monkeypatch):
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda *_a, **_k: _source())
    monkeypatch.setattr(refill, "run_daily_feature_backfill", lambda *_a, **_k: _feature("daily", "FAILED"))
    monkeypatch.setattr(refill, "run_intraday_feature_backfill", lambda *_a, **_k: _feature("intraday", "FAILED"))
    assert refill.run_refill_pipeline("01/07/2026", "02/07/2026", "SSI")["status"] == "FAILED"


def test_weekend_only_is_no_op_and_does_not_call_features(monkeypatch):
    monkeypatch.setattr(refill, "run_backfill_pipeline", lambda *_a, **_k: _source(processed_days=0))
    monkeypatch.setattr(refill, "run_daily_feature_backfill", lambda *_a, **_k: pytest.fail("daily called"))
    monkeypatch.setattr(refill, "run_intraday_feature_backfill", lambda *_a, **_k: pytest.fail("intraday called"))
    result = refill.run_refill_pipeline("04/07/2026", "05/07/2026", "SSI")
    assert result["status"] == "OK" and result["no_op"] is True
    assert "weekends only" in result["stages"]["features_daily"]["reason"]


def test_orchestrator_has_no_delete_replace_or_downstream_calls():
    source = open(refill.__file__, encoding="utf-8").read().lower()
    for forbidden in ("delete(", "atomic_replace", "signal", "backtest", "analog"):
        assert forbidden not in source
