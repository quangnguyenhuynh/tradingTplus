from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterator

from src.pipeline.date_utils import parse_ddmmyyyy, parse_iso_date, validate_not_future
from src.pipeline.eod import run_eod_pipeline


def _parse_backfill_date(value: str):
    """Parse the production DD/MM/YYYY format and legacy ISO compatibility input."""
    text = str(value).strip()
    if not text:
        raise ValueError("Backfill date must not be empty")
    if "/" in text:
        return parse_ddmmyyyy(text)
    return parse_iso_date(text)


def _iter_calendar_dates(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _failed_day_summary(date_text: str, exc: Exception) -> dict[str, Any]:
    message = str(exc) or exc.__class__.__name__
    return {
        "flow": "eod",
        "date": date_text,
        "daily_summary": None,
        "intraday_summary": None,
        "ingest_summary": None,
        "status": "FAILED",
        "failures": [message],
        "warnings": [],
        "error": message,
    }


def _aggregate_status(day_summaries: list[dict[str, Any]]) -> str:
    statuses = [str(summary.get("status") or "FAILED").upper() for summary in day_summaries]
    if statuses and all(status == "OK" for status in statuses):
        return "OK"
    if statuses and all(status == "FAILED" for status in statuses):
        return "FAILED"
    return "PARTIAL"


def run_backfill_pipeline(from_date: str, to_date: str) -> dict[str, Any]:
    """Run the production EOD ingest/check flow for every weekday in a date range.

    Backfill is an orchestration layer only. Each processed date delegates to
    ``run_eod_pipeline`` so daily ingest, intraday ingest, and completeness checks
    keep the same production boundaries and status contract as a normal EOD run.
    Features, signals, and backtests are never triggered.
    """
    start = _parse_backfill_date(from_date)
    end = _parse_backfill_date(to_date)
    validate_not_future(start)
    validate_not_future(end)
    if start.date > end.date:
        raise ValueError("from_date must be <= to_date")

    calendar_dates = list(_iter_calendar_dates(start.date, end.date))
    weekdays = [value for value in calendar_dates if value.weekday() < 5]
    skipped_weekends = [value.strftime("%d/%m/%Y") for value in calendar_dates if value.weekday() >= 5]
    if not weekdays:
        raise ValueError("Backfill range contains no weekdays")

    print(f"🚀 Backfill EOD from {start.ddmmyyyy} to {end.ddmmyyyy}")
    print(f"📅 Weekdays to process: {len(weekdays)}; weekends skipped: {len(skipped_weekends)}")

    day_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for current in weekdays:
        date_text = current.strftime("%d/%m/%Y")
        print(f"\n▶️ Backfill EOD {date_text}")
        try:
            summary = run_eod_pipeline(date_text)
            if not isinstance(summary, dict):
                raise RuntimeError("run_eod_pipeline returned a non-dict summary")
        except Exception as exc:
            summary = _failed_day_summary(date_text, exc)
            errors.append({"date": date_text, "error": summary["error"]})
            print(f"❌ Backfill EOD {date_text} failed: {summary['error']}")
        day_summaries.append(summary)

    ok_days = sum(1 for summary in day_summaries if summary.get("status") == "OK")
    partial_days = sum(1 for summary in day_summaries if summary.get("status") == "PARTIAL")
    failed_days = sum(1 for summary in day_summaries if summary.get("status") == "FAILED")
    status = _aggregate_status(day_summaries)

    result = {
        "flow": "backfill",
        "from_date": start.ddmmyyyy,
        "to_date": end.ddmmyyyy,
        "requested_calendar_days": len(calendar_dates),
        "processed_days": len(day_summaries),
        "skipped_weekend_days": len(skipped_weekends),
        "skipped_weekend_dates": skipped_weekends,
        "ok_days": ok_days,
        "partial_days": partial_days,
        "failed_days": failed_days,
        "error_count": len(errors),
        "errors": errors,
        "day_summaries": day_summaries,
        "status": status,
    }
    print(
        f"\n{'✅' if status == 'OK' else '⚠️' if status == 'PARTIAL' else '❌'} "
        f"Backfill status {status}: OK={ok_days}, PARTIAL={partial_days}, FAILED={failed_days}"
    )
    return result


def backfill(from_date: str, to_date: str, symbols: list | None = None, allow_future: bool = False) -> dict[str, Any]:
    """Backward-compatible function name for the new full-market EOD backfill.

    Legacy ISO dates remain accepted. Symbol-scoped and future-date writes are
    intentionally rejected because the production EOD flow operates on the full
    active universe and its ingest commands enforce safe write dates.
    """
    if symbols:
        raise ValueError("Symbol-scoped backfill is not supported by the EOD-style production backfill")
    if allow_future:
        raise ValueError("Future-date backfill is not supported by the EOD-style production backfill")
    return run_backfill_pipeline(from_date, to_date)
