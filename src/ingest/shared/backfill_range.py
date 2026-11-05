"""Shared inclusive backfill date ranges and report aggregation; no provider calls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from src.ingest.shared.date_utils import parse_ddmmyyyy, validate_not_future


@dataclass(frozen=True)
class _BackfillRange:
    from_date: str
    to_date: str
    requested_calendar_days: int
    eligible_dates: tuple[str, ...]
    skipped_weekend_dates: tuple[str, ...]


def _resolve_range(from_date: str, to_date: str) -> _BackfillRange:
    """Validate and enumerate one inclusive range without guessing holidays."""
    start = parse_ddmmyyyy(from_date)
    end = parse_ddmmyyyy(to_date)
    validate_not_future(start)
    validate_not_future(end)
    if start.date > end.date:
        raise ValueError("from_date must be <= to_date")

    eligible: list[str] = []
    weekends: list[str] = []
    current: date = start.date
    while current <= end.date:
        date_text = current.strftime("%d/%m/%Y")
        (weekends if current.weekday() >= 5 else eligible).append(date_text)
        current += timedelta(days=1)
    return _BackfillRange(
        from_date=start.ddmmyyyy,
        to_date=end.ddmmyyyy,
        requested_calendar_days=(end.date - start.date).days + 1,
        eligible_dates=tuple(eligible),
        skipped_weekend_dates=tuple(weekends),
    )


def _range_status(*, processed_days: int, ok_days: int, partial_days: int, failed_days: int) -> str:
    """Aggregate day statuses; an empty weekend-only range is a successful no-op."""
    if processed_days == 0 or ok_days == processed_days:
        return "OK"
    if failed_days == processed_days:
        return "FAILED"
    if partial_days or ok_days or failed_days:
        return "PARTIAL"
    return "FAILED"


def _failure_day(flow: str, date_text: str, exc: Exception) -> dict[str, Any]:
    return {"flow": flow, "date": date_text, "status": "FAILED", "error": str(exc)}


def _base_range_summary(
    *,
    flow: str,
    date_range: _BackfillRange,
    requested_symbols: list[str] | None,
    day_summaries: list[dict[str, Any]],
    errors: list[dict[str, str]],
    resolved_symbols: list[str] | None = None,
) -> dict[str, Any]:
    counts = {status: sum(item.get("status") == status for item in day_summaries) for status in ("OK", "PARTIAL", "FAILED")}
    if resolved_symbols is None:
        resolved_symbols = requested_symbols
    if resolved_symbols is None:
        for summary in day_summaries:
            if isinstance(summary.get("symbols"), list):
                resolved_symbols = summary["symbols"]
                break
    return {
        "flow": flow,
        "from_date": date_range.from_date,
        "to_date": date_range.to_date,
        "symbol_scope": "EXPLICIT" if requested_symbols is not None else "ALL_ACTIVE",
        "requested_symbols": requested_symbols,
        "symbols": resolved_symbols,
        "symbol_count": len(resolved_symbols) if resolved_symbols is not None else 0,
        "requested_calendar_days": date_range.requested_calendar_days,
        "processed_days": len(day_summaries),
        "skipped_weekend_days": len(date_range.skipped_weekend_dates),
        "skipped_weekend_dates": list(date_range.skipped_weekend_dates),
        "ok_days": counts["OK"],
        "partial_days": counts["PARTIAL"],
        "failed_days": counts["FAILED"],
        "error_count": len(errors),
        "errors": errors,
        "day_summaries": day_summaries,
        "status": _range_status(
            processed_days=len(day_summaries),
            ok_days=counts["OK"],
            partial_days=counts["PARTIAL"],
            failed_days=counts["FAILED"],
        ),
    }
