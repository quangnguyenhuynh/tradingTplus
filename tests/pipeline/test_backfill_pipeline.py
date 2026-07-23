import importlib

import pytest

pipeline = importlib.import_module("src.pipeline.backfill")


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
        ("run_intraday_backfill_pipeline", "run_intraday_ingest", "backfill-intraday", "intraday_summary"),
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
        ("run_intraday_backfill_pipeline", "run_intraday_ingest"),
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


@pytest.mark.parametrize("runner_name", ["run_daily_backfill_pipeline", "run_intraday_backfill_pipeline", "run_backfill_pipeline"])
def test_shared_range_rejections_and_weekend_noop(monkeypatch, runner_name):
    runner = getattr(pipeline, runner_name)
    with pytest.raises(ValueError, match="from_date must be <= to_date"):
        runner("14/07/2026", "13/07/2026")
    monkeypatch.setattr(pipeline, "validate_not_future", lambda value: (_ for _ in ()).throw(ValueError("future")))
    with pytest.raises(ValueError, match="future"):
        runner("13/07/2026", "13/07/2026")


def test_weekend_only_ranges_are_successful_noops(monkeypatch):
    monkeypatch.setattr(pipeline, "run_daily_ingest", lambda *a, **k: pytest.fail("daily must not run"))
    monkeypatch.setattr(pipeline, "run_intraday_ingest", lambda *a, **k: pytest.fail("intraday must not run"))
    monkeypatch.setattr(pipeline, "check_ingest", lambda *a, **k: pytest.fail("check must not run"))
    for runner in (pipeline.run_daily_backfill_pipeline, pipeline.run_intraday_backfill_pipeline, pipeline.run_backfill_pipeline):
        result = runner("18/07/2026", "19/07/2026")
        assert result["processed_days"] == 0
        assert result["skipped_weekend_days"] == 2
        assert result["status"] == "OK"


@pytest.mark.parametrize("runner_name", ["run_daily_backfill_pipeline", "run_intraday_backfill_pipeline", "run_backfill_pipeline"])
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


def test_intraday_branch_preserves_partial_status_and_calls_nothing_else(monkeypatch):
    monkeypatch.setattr(pipeline, "run_intraday_ingest", lambda date, symbols=None: _intraday(date, "PARTIAL") | {"daily_context_missing_count": 1})
    monkeypatch.setattr(pipeline, "run_daily_ingest", lambda *a, **k: pytest.fail("daily must not run"))
    monkeypatch.setattr(pipeline, "check_ingest", lambda *a, **k: pytest.fail("check must not run"))
    result = pipeline.run_intraday_backfill_pipeline("13/07/2026", "13/07/2026")
    assert result["status"] == "PARTIAL"
    assert result["day_summaries"][0]["intraday_summary"]["daily_context_missing_count"] == 1


def test_combined_runs_complete_branches_in_order_then_checks_each_date(monkeypatch):
    calls = []

    def daily_branch(start, end, symbols=None):
        calls.append(("daily-branch", symbols))
        return pipeline._base_range_summary(
            flow="backfill-daily", date_range=pipeline._resolve_range(start, end), requested_symbols=symbols,
            day_summaries=[{"flow": "backfill-daily-day", "date": date, "daily_summary": _daily(date), "status": "OK"} for date in ("13/07/2026", "14/07/2026")], errors=[])

    def intraday_branch(start, end, symbols=None):
        calls.append(("intraday-branch", symbols))
        return pipeline._base_range_summary(
            flow="backfill-intraday", date_range=pipeline._resolve_range(start, end), requested_symbols=symbols,
            day_summaries=[{"flow": "backfill-intraday-day", "date": date, "intraday_summary": _intraday(date), "status": "OK"} for date in ("13/07/2026", "14/07/2026")], errors=[])

    monkeypatch.setattr(pipeline, "run_daily_backfill_pipeline", daily_branch)
    monkeypatch.setattr(pipeline, "run_intraday_backfill_pipeline", intraday_branch)
    monkeypatch.setattr(pipeline, "check_ingest", lambda date, symbols=None: calls.append(("check", date, symbols)) or _complete(date))

    result = pipeline.run_backfill_pipeline("13/07/2026", "14/07/2026", symbols=["ssi", " HPG ", "SSI"])
    fixed_scope = calls[0][1]
    assert calls == [
        ("daily-branch", fixed_scope),
        ("intraday-branch", fixed_scope),
        ("check", "13/07/2026", fixed_scope),
        ("check", "14/07/2026", fixed_scope),
    ]
    assert fixed_scope == ["SSI", "HPG"]
    assert calls[0][1] is calls[1][1] is calls[2][2] is calls[3][2]
    assert result["flow"] == "backfill"
    assert result["daily_backfill_summary"]["flow"] == "backfill-daily"
    assert result["intraday_backfill_summary"]["flow"] == "backfill-intraday"
    assert all(item["flow"] == "backfill-day" for item in result["day_summaries"])
    assert result["status"] == "OK"


def test_combined_completeness_failure_is_visible_and_later_dates_continue(monkeypatch):
    monkeypatch.setattr(pipeline, "run_daily_ingest", lambda date, symbols=None: _daily(date))
    monkeypatch.setattr(pipeline, "run_intraday_ingest", lambda date, symbols=None: _intraday(date))
    calls = []

    def check(date, symbols=None):
        calls.append(date)
        if date == "13/07/2026":
            raise RuntimeError("database unavailable")
        return _complete(date)

    monkeypatch.setattr(pipeline, "check_ingest", check)
    result = pipeline.run_backfill_pipeline("13/07/2026", "14/07/2026")
    assert calls == ["13/07/2026", "14/07/2026"]
    assert result["status"] == "PARTIAL"
    assert result["errors"] == [{"date": "13/07/2026", "branch": "completeness", "error": "database unavailable"}]
    assert result["day_summaries"][0]["daily_summary"]["status"] == "OK"
    assert result["day_summaries"][0]["intraday_summary"]["status"] == "OK"


def test_combined_uses_eod_compatible_failure_and_partial_semantics(monkeypatch):
    monkeypatch.setattr(pipeline, "run_daily_ingest", lambda date, symbols=None: _daily(date))
    monkeypatch.setattr(pipeline, "run_intraday_ingest", lambda date, symbols=None: _intraday(date, "PARTIAL"))
    monkeypatch.setattr(pipeline, "check_ingest", lambda date, symbols=None: _complete(date, "PARTIAL") | {"missing_intraday_count": 1})
    assert pipeline.run_backfill_pipeline("13/07/2026", "13/07/2026")["status"] == "PARTIAL"

    monkeypatch.setattr(pipeline, "check_ingest", lambda date, symbols=None: _complete(date, "FAILED") | {"stock_daily_count": 0})
    result = pipeline.run_backfill_pipeline("13/07/2026", "13/07/2026")
    assert result["status"] == "FAILED"
    assert "stock_daily_count == 0" in result["day_summaries"][0]["failures"]


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
