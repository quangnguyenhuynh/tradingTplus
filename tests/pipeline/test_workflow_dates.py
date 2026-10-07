from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.pipeline import workflow_dates

VN = ZoneInfo("Asia/Ho_Chi_Minh")


@pytest.mark.parametrize(("pipeline", "runtime", "slot", "target"), [
    ("stock-eod", "2026-10-07T16:40", "2026-10-07T16:30", "07/10/2026"),
    ("stock-eod", "2026-10-08T01:30", "2026-10-07T16:30", "07/10/2026"),
    ("stock-intraday", "2026-10-07T17:10", "2026-10-07T17:00", "07/10/2026"),
    ("stock-intraday", "2026-10-08T01:30", "2026-10-07T17:00", "07/10/2026"),
    ("index", "2026-10-08T08:40", "2026-10-08T08:30", "07/10/2026"),
    ("index", "2026-10-08T14:00", "2026-10-08T08:30", "07/10/2026"),
    ("index", "2026-10-08T10:00", "2026-10-08T08:30", "07/10/2026"),
    ("index", "2026-10-10T08:30", "2026-10-10T08:30", "09/10/2026"),
    ("index", "2026-10-06T08:29", "2026-10-03T08:30", "02/10/2026"),
    ("stock-eod", "2026-10-12T16:29", "2026-10-09T16:30", "09/10/2026"),
    ("stock-intraday", "2026-10-12T16:45", "2026-10-09T17:00", "09/10/2026"),
    ("stock-intraday", "2026-10-07T17:00", "2026-10-07T17:00", "07/10/2026"),
])
def test_scheduled_slot_and_target(pipeline, runtime, slot, target):
    now = datetime.fromisoformat(runtime).replace(tzinfo=VN)
    result = workflow_dates.resolve_workflow_date(pipeline, "schedule", now=now)
    assert result.runtime_vn == now
    assert result.scheduled_slot_vn == datetime.fromisoformat(slot).replace(tzinfo=VN)
    assert result.target_date == target
    assert result.target_source == "scheduled"
    # UTC representation must select the same Vietnam-local slot.
    assert workflow_dates.resolve_workflow_date(
        pipeline, "schedule", now=now.astimezone(timezone.utc)
    ) == result


@pytest.mark.parametrize("pipeline", ["stock", "stock-eod", "stock-intraday", "index"])
@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
@pytest.mark.parametrize("date", ["07/10/2026", "2026-10-07"])
def test_manual_explicit_date_wins(pipeline, event, date):
    result = workflow_dates.resolve_workflow_date(
        pipeline, event, date, now=datetime(2026, 10, 8, 10, tzinfo=VN)
    )
    assert result.target_date == date
    assert result.target_source == "manual"
    assert result.scheduled_slot_vn is None


@pytest.mark.parametrize(("pipeline", "target"), [
    ("stock", "08/10/2026"), ("stock-eod", "08/10/2026"),
    ("stock-intraday", "08/10/2026"), ("index", "07/10/2026"),
])
def test_no_input_manual_defaults_are_preserved(pipeline, target):
    result = workflow_dates.resolve_workflow_date(
        pipeline, "workflow_dispatch", now=datetime(2026, 10, 8, 1, 30, tzinfo=VN)
    )
    assert result.target_date == target
    assert result.target_source == "default"
    assert result.scheduled_slot_vn is None


def test_invalid_manual_date_is_rejected():
    with pytest.raises(ValueError):
        workflow_dates.resolve_workflow_date("stock-intraday", "workflow_dispatch", "31/02/2026")


def test_resolver_cli_logs_all_timing_fields(monkeypatch, capsys):
    now = datetime(2026, 10, 8, 1, 30, tzinfo=VN)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz)
    monkeypatch.setattr(workflow_dates, "datetime", Clock)
    monkeypatch.setattr("sys.argv", ["workflow_dates", "stock-intraday", "--event", "schedule"])
    assert workflow_dates.main() == 0
    assert capsys.readouterr().out.splitlines() == [
        "event=schedule",
        "runtime_vn=2026-10-08T01:30:00+07:00",
        "scheduled_slot_vn=2026-10-07T17:00:00+07:00",
        "target_date=07/10/2026",
        "target_source=scheduled",
    ]
