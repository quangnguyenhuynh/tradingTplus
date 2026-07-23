import importlib

import pytest

pipeline = importlib.import_module("src.pipeline.backfill")


def _summary(date_text: str, status: str = "OK") -> dict:
    return {"flow": "eod", "date": date_text, "status": status, "marker": date_text}


def test_calls_eod_once_for_each_weekday_and_preserves_summaries(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "run_eod_pipeline", lambda value: calls.append(value) or _summary(value))
    result = pipeline.run_backfill_pipeline("10/07/2026", "14/07/2026")
    assert calls == ["10/07/2026", "13/07/2026", "14/07/2026"]
    assert result["day_summaries"] == [_summary(value) for value in calls]
    assert result["requested_calendar_days"] == 5
    assert result["processed_days"] == 3
    assert result["skipped_weekend_dates"] == ["11/07/2026", "12/07/2026"]
    assert result["skipped_weekend_days"] == 2
    assert result["status"] == "OK"


def test_mixed_and_partial_statuses_produce_partial(monkeypatch):
    statuses = iter(["OK", "FAILED", "PARTIAL"])
    monkeypatch.setattr(pipeline, "run_eod_pipeline", lambda value: _summary(value, next(statuses)))
    result = pipeline.run_backfill_pipeline("13/07/2026", "15/07/2026")
    assert (result["ok_days"], result["failed_days"], result["partial_days"]) == (1, 1, 1)
    assert result["status"] == "PARTIAL"


def test_all_failed_produces_failed(monkeypatch):
    monkeypatch.setattr(pipeline, "run_eod_pipeline", lambda value: _summary(value, "FAILED"))
    result = pipeline.run_backfill_pipeline("13/07/2026", "14/07/2026")
    assert result["failed_days"] == 2
    assert result["status"] == "FAILED"


def test_exception_is_recorded_and_later_dates_continue(monkeypatch):
    calls = []

    def run(value):
        calls.append(value)
        if value == "13/07/2026":
            raise RuntimeError("SSI unavailable")
        return _summary(value)

    monkeypatch.setattr(pipeline, "run_eod_pipeline", run)
    result = pipeline.run_backfill_pipeline("13/07/2026", "14/07/2026")
    assert calls == ["13/07/2026", "14/07/2026"]
    assert result["status"] == "PARTIAL"
    assert result["error_count"] == 1
    assert result["errors"] == [{"date": "13/07/2026", "error": "SSI unavailable"}]
    assert result["day_summaries"][0]["status"] == "FAILED"


def test_reversed_range_is_rejected():
    with pytest.raises(ValueError, match="from_date must be <= to_date"):
        pipeline.run_backfill_pipeline("14/07/2026", "13/07/2026")


def test_future_range_is_rejected(monkeypatch):
    monkeypatch.setattr(pipeline, "validate_not_future", lambda value: (_ for _ in ()).throw(ValueError("future")))
    with pytest.raises(ValueError, match="future"):
        pipeline.run_backfill_pipeline("13/07/2026", "13/07/2026")


def test_weekend_only_range_is_successful_noop(monkeypatch):
    monkeypatch.setattr(pipeline, "run_eod_pipeline", lambda value: pytest.fail("EOD must not run on weekends"))
    result = pipeline.run_backfill_pipeline("18/07/2026", "19/07/2026")
    assert result["processed_days"] == 0
    assert result["skipped_weekend_days"] == 2
    assert result["day_summaries"] == []
    assert result["status"] == "OK"


def test_compatibility_wrapper_delegates_and_converts_iso_dates(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "run_backfill_pipeline", lambda start, end: captured.update(start=start, end=end) or {"status": "OK"})
    with pytest.deprecated_call():
        result = pipeline.backfill("2026-07-13", "2026-07-14")
    assert captured == {"start": "13/07/2026", "end": "14/07/2026"}
    assert result == {"status": "OK"}


def test_compatibility_wrapper_rejects_unsupported_scope():
    with pytest.deprecated_call(), pytest.raises(ValueError, match="symbol-scoped"):
        pipeline.backfill("2026-07-13", "2026-07-14", symbols=["SSI"])


def test_module_has_no_duplicate_ingest_dependencies():
    source = open(pipeline.__file__, encoding="utf-8").read()
    for forbidden in ("SSIApi", "SupabaseClient", "fetch_one_day", "feature_engine", "signal", "backtest"):
        assert forbidden not in source
