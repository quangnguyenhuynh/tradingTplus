import importlib

import pytest

pipeline = importlib.import_module("src.ingest.maintenance.backfill")


def _daily(date_text: str, status: str = "OK") -> dict:
    return {"date": date_text, "status": status, "symbol_count": 2, "error_count": 0, "symbols": ["SSI", "HPG"]}


def _intraday(date_text: str, status: str = "OK") -> dict:
    return {"date": date_text, "status": status, "symbol_count": 2, "error_count": 0, "symbols": ["SSI", "HPG"]}


def _complete(date_text: str, status: str = "OK") -> dict:
    return {
        "date": date_text,
        "status": status,
        "symbol_count": 2,
        "symbols": ["SSI", "HPG"],
        "stock_daily_count": 2,
        "stock_intraday_count": 200,
        "missing_stock_daily_count": 0,
        "missing_intraday_count": 0,
        "incomplete_intraday_count": 0,
    }


@pytest.mark.parametrize(
    ("runner_name", "ingest_name", "flow", "result_key"),
    [
        ("run_daily_backfill_pipeline", "run_daily_ingest", "backfill-daily", "daily_summary"),
    ],
)
def test_branch_inclusive_range_weekends_and_fixed_symbol_scope(monkeypatch, runner_name, ingest_name, flow, result_key):
    calls = []
    summary_factory = _daily if ingest_name == "run_daily_ingest" else _intraday
    monkeypatch.setattr(pipeline, ingest_name, lambda value, symbols=None: calls.append((value, symbols)) or summary_factory(value))

    result = getattr(pipeline, runner_name)("10/07/2026", "14/07/2026", symbols=["ssi", " HPG ", "SSI"])

    assert [date for date, _ in calls] == ["10/07/2026", "13/07/2026", "14/07/2026"]
    assert all(symbols == ["SSI", "HPG"] for _, symbols in calls)
    assert calls[0][1] is calls[1][1] is calls[2][1]
    assert result["flow"] == flow
    assert result["requested_calendar_days"] == 5
    assert result["processed_days"] == 3
    assert result["skipped_weekend_dates"] == ["11/07/2026", "12/07/2026"]
    assert all(result_key in item for item in result["day_summaries"])
    assert result["status"] == "OK"


@pytest.mark.parametrize(
    ("runner_name", "ingest_name"),
    [
        ("run_daily_backfill_pipeline", "run_daily_ingest"),
    ],
)
def test_branch_exception_is_recorded_and_later_dates_continue(monkeypatch, runner_name, ingest_name):
    calls = []
    factory = _daily if ingest_name == "run_daily_ingest" else _intraday

    def ingest(value, symbols=None):
        calls.append(value)
        if value == "13/07/2026":
            raise RuntimeError("SSI unavailable")
        return factory(value)

    monkeypatch.setattr(pipeline, ingest_name, ingest)
    result = getattr(pipeline, runner_name)("13/07/2026", "14/07/2026")
    assert calls == ["13/07/2026", "14/07/2026"]
    assert result["status"] == "PARTIAL"
    assert result["errors"] == [{"date": "13/07/2026", "error": "SSI unavailable"}]
    assert result["day_summaries"][0]["status"] == "FAILED"


@pytest.mark.parametrize("runner_name", ["run_daily_backfill_pipeline"])
def test_shared_range_rejections_and_weekend_noop(monkeypatch, runner_name):
    runner = getattr(pipeline, runner_name)
    with pytest.raises(ValueError, match="from_date must be <= to_date"):
        runner("14/07/2026", "13/07/2026")
    monkeypatch.setattr(pipeline, "validate_not_future", lambda value: (_ for _ in ()).throw(ValueError("future")))
    with pytest.raises(ValueError, match="future"):
        runner("13/07/2026", "13/07/2026")




@pytest.mark.parametrize("runner_name", ["run_daily_backfill_pipeline"])
def test_explicit_empty_scope_fails_before_pipeline_calls(monkeypatch, runner_name):
    monkeypatch.setattr(pipeline, "run_daily_ingest", lambda *a, **k: pytest.fail("must not run"))
    monkeypatch.setattr(pipeline, "run_intraday_ingest", lambda *a, **k: pytest.fail("must not run"))
    monkeypatch.setattr(pipeline, "check_ingest", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError, match="Explicit symbol scope"):
        getattr(pipeline, runner_name)("13/07/2026", "14/07/2026", symbols=[])


def test_daily_branch_does_not_call_other_branches_or_completeness(monkeypatch):
    monkeypatch.setattr(pipeline, "run_daily_ingest", lambda date, symbols=None: _daily(date))
    monkeypatch.setattr(pipeline, "run_intraday_ingest", lambda *a, **k: pytest.fail("intraday must not run"))
    monkeypatch.setattr(pipeline, "check_ingest", lambda *a, **k: pytest.fail("check must not run"))
    assert pipeline.run_daily_backfill_pipeline("13/07/2026", "13/07/2026")["status"] == "OK"


def test_multi_day_daily_backfill_never_synchronizes_master_data(monkeypatch):
    calls = []

    def daily(date, symbols=None):
        calls.append(date)
        return _daily(date)

    monkeypatch.setattr(pipeline, "run_daily_ingest", daily)
    # Master synchronization is intentionally not an orchestration dependency.
    assert not hasattr(pipeline, "sync_indexes")
    assert not hasattr(pipeline, "sync_index_components")

    result = pipeline.run_daily_backfill_pipeline("13/07/2026", "15/07/2026", symbols=["SSI"])

    assert calls == ["13/07/2026", "14/07/2026", "15/07/2026"]
    assert result["processed_days"] == 3










def test_compatibility_wrapper_delegates_converts_iso_and_rejects_future_override(monkeypatch):
    captured = {}
    monkeypatch.setattr(pipeline, "run_backfill_pipeline", lambda start, end, symbols=None: captured.update(start=start, end=end, symbols=symbols) or {"status": "OK"})
    with pytest.deprecated_call():
        result = pipeline.backfill("2026-07-13", "2026-07-14", symbols=["ssi"])
    assert captured == {"start": "13/07/2026", "end": "14/07/2026", "symbols": ["ssi"]}
    assert result == {"status": "OK"}
    with pytest.deprecated_call(), pytest.raises(ValueError, match="unsupported"):
        pipeline.backfill("2026-07-13", "2026-07-14", allow_future=True)


def test_module_has_no_eod_or_downstream_engine_dependency():
    source = open(pipeline.__file__, encoding="utf-8").read()
    for forbidden in ("run_eod_pipeline", "feature_engine", "signal_engine", "backtest_engine"):
        assert forbidden not in source


@pytest.mark.parametrize("name", ["run_backfill_pipeline", "run_intraday_backfill_pipeline"])
def test_unavailable_backfill_never_starts_daily_or_completeness(monkeypatch, name):
    from src.providers.ssi.capabilities import CapabilityUnavailableError
    def fail(*args, **kwargs): raise AssertionError("partial work")
    monkeypatch.setattr(pipeline, "run_daily_ingest", fail)
    monkeypatch.setattr(pipeline, "check_ingest", fail)
    with pytest.raises(CapabilityUnavailableError):
        getattr(pipeline, name)("10/07/2026", "14/07/2026", symbols=["SSI"])
