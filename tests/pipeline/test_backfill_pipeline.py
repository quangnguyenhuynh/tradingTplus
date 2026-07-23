from __future__ import annotations

import importlib

import pytest

backfill = importlib.import_module("src.pipeline.backfill")


def _eod_summary(date_text: str, status: str = "OK") -> dict:
    return {
        "flow": "eod",
        "date": date_text,
        "daily_summary": {"status": status},
        "intraday_summary": {"status": status},
        "ingest_summary": {"status": status},
        "status": status,
        "failures": [],
        "warnings": [],
    }


def test_backfill_runs_eod_for_each_weekday_and_skips_weekend(monkeypatch):
    calls = []
    monkeypatch.setattr(
        backfill,
        "run_eod_pipeline",
        lambda date_text: calls.append(date_text) or _eod_summary(date_text),
    )

    summary = backfill.run_backfill_pipeline("03/07/2026", "06/07/2026")

    assert calls == ["03/07/2026", "06/07/2026"]
    assert summary["requested_calendar_days"] == 4
    assert summary["processed_days"] == 2
    assert summary["skipped_weekend_dates"] == ["04/07/2026", "05/07/2026"]
    assert summary["ok_days"] == 2
    assert summary["partial_days"] == 0
    assert summary["failed_days"] == 0
    assert summary["status"] == "OK"


def test_backfill_aggregates_day_statuses(monkeypatch):
    statuses = {
        "06/07/2026": "OK",
        "07/07/2026": "PARTIAL",
        "08/07/2026": "FAILED",
    }
    monkeypatch.setattr(
        backfill,
        "run_eod_pipeline",
        lambda date_text: _eod_summary(date_text, statuses[date_text]),
    )

    summary = backfill.run_backfill_pipeline("06/07/2026", "08/07/2026")

    assert summary["ok_days"] == 1
    assert summary["partial_days"] == 1
    assert summary["failed_days"] == 1
    assert summary["status"] == "PARTIAL"
    assert [day["status"] for day in summary["day_summaries"]] == ["OK", "PARTIAL", "FAILED"]


def test_backfill_continues_after_one_date_raises(monkeypatch):
    calls = []

    def fake_eod(date_text):
        calls.append(date_text)
        if date_text == "06/07/2026":
            raise RuntimeError("temporary SSI failure")
        return _eod_summary(date_text)

    monkeypatch.setattr(backfill, "run_eod_pipeline", fake_eod)

    summary = backfill.run_backfill_pipeline("06/07/2026", "07/07/2026")

    assert calls == ["06/07/2026", "07/07/2026"]
    assert summary["failed_days"] == 1
    assert summary["ok_days"] == 1
    assert summary["error_count"] == 1
    assert summary["errors"] == [{"date": "06/07/2026", "error": "temporary SSI failure"}]
    assert summary["day_summaries"][0]["status"] == "FAILED"
    assert summary["status"] == "PARTIAL"


def test_backfill_all_failed_returns_failed(monkeypatch):
    monkeypatch.setattr(
        backfill,
        "run_eod_pipeline",
        lambda date_text: _eod_summary(date_text, "FAILED"),
    )

    summary = backfill.run_backfill_pipeline("06/07/2026", "07/07/2026")

    assert summary["failed_days"] == 2
    assert summary["status"] == "FAILED"


def test_backfill_rejects_reversed_range():
    with pytest.raises(ValueError, match="from_date must be <= to_date"):
        backfill.run_backfill_pipeline("08/07/2026", "06/07/2026")


def test_backfill_rejects_future_range():
    with pytest.raises(ValueError, match="future"):
        backfill.run_backfill_pipeline("01/01/2999", "02/01/2999")


def test_backfill_rejects_weekend_only_range():
    with pytest.raises(ValueError, match="contains no weekdays"):
        backfill.run_backfill_pipeline("04/07/2026", "05/07/2026")


def test_legacy_backfill_accepts_iso_dates_but_rejects_old_unsafe_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(
        backfill,
        "run_eod_pipeline",
        lambda date_text: calls.append(date_text) or _eod_summary(date_text),
    )

    summary = backfill.backfill("2026-07-06", "2026-07-06")

    assert calls == ["06/07/2026"]
    assert summary["status"] == "OK"
    with pytest.raises(ValueError, match="Symbol-scoped"):
        backfill.backfill("2026-07-06", "2026-07-06", symbols=["SSI"])
    with pytest.raises(ValueError, match="Future-date"):
        backfill.backfill("2026-07-06", "2026-07-06", allow_future=True)
