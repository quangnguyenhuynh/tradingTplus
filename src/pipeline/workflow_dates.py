"""Resolve EOD workflow dates from Vietnam-local schedule slots."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from src.pipeline.date_utils import VN_TZ, latest_weekday_on_or_before, parse_ddmmyyyy


@dataclass(frozen=True)
class WorkflowDateResolution:
    runtime_vn: datetime
    target_date: str
    target_source: str


def _latest_schedule_slot(
    runtime_vn: datetime,
    *,
    weekdays: set[int],
    scheduled_time: time,
) -> datetime:
    """Return the latest configured Vietnam-local slot not after runtime."""
    for days_ago in range(8):
        candidate_date = runtime_vn.date() - timedelta(days=days_ago)
        if candidate_date.weekday() not in weekdays:
            continue
        candidate = datetime.combine(candidate_date, scheduled_time, tzinfo=VN_TZ)
        if candidate <= runtime_vn:
            return candidate
    raise RuntimeError("Could not resolve a schedule slot in the preceding week")


def resolve_workflow_date(
    pipeline: str,
    event_name: str,
    manual_date: str | None = None,
    *,
    now: datetime | None = None,
) -> WorkflowDateResolution:
    """Resolve a Stock or Index EOD target without using a delayed run's date naively."""
    runtime_vn = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)
    supplied_date = (manual_date or "").strip()
    if supplied_date:
        parse_ddmmyyyy(supplied_date)
        return WorkflowDateResolution(
            runtime_vn=runtime_vn,
            target_date=supplied_date,
            target_source="manual",
        )

    if event_name == "schedule":
        if pipeline == "stock":
            slot = _latest_schedule_slot(
                runtime_vn, weekdays={0, 1, 2, 3, 4}, scheduled_time=time(16, 30)
            )
            target = slot.date()
        elif pipeline == "index":
            slot = _latest_schedule_slot(
                runtime_vn, weekdays={1, 2, 3, 4, 5}, scheduled_time=time(8, 7)
            )
            target = slot.date() - timedelta(days=1)
        else:
            raise ValueError(f"Unsupported pipeline: {pipeline!r}")
        source = "scheduled"
    elif pipeline == "stock":
        target = latest_weekday_on_or_before(runtime_vn)
        source = "default"
    elif pipeline == "index":
        # Preserve the workflow's existing no-input manual behavior.
        target = runtime_vn.date() - timedelta(days=1)
        source = "default"
    else:
        raise ValueError(f"Unsupported pipeline: {pipeline!r}")

    return WorkflowDateResolution(runtime_vn, target.strftime("%d/%m/%Y"), source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline", choices=("stock", "index"))
    parser.add_argument("--event", required=True)
    parser.add_argument("--manual-date", default="")
    args = parser.parse_args()
    result = resolve_workflow_date(args.pipeline, args.event, args.manual_date)
    print(f"runtime_vn={result.runtime_vn.isoformat()}")
    print(f"target_date={result.target_date}")
    print(f"target_source={result.target_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
