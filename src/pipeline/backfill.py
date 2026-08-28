"""Independent daily/intraday historical source-data backfill orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable
from warnings import warn

from src.pipeline.daily import run_daily_ingest
from src.pipeline.date_utils import parse_ddmmyyyy, parse_iso_date, validate_not_future
from src.pipeline.pipeline_status import status_from_ingest as _status_from_ingest, validate_pipeline_summary as _validate_pipeline_summary
from src.pipeline.ingest_check import check_ingest
from src.pipeline.intraday_ingest import run_intraday_ingest
from src.pipeline.symbol_scope import normalize_symbol_scope


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


def _run_ingest_backfill(
    *,
    flow: str,
    day_flow: str,
    date_range: _BackfillRange,
    requested_symbols: list[str] | None,
    ingest: Callable[..., dict[str, Any]],
    result_key: str,
) -> dict[str, Any]:
    day_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for date_text in date_range.eligible_dates:
        try:
            ingest_summary = ingest(date_text, symbols=requested_symbols)
            status = ingest_summary.get("status") if isinstance(ingest_summary, dict) else None
            if status not in {"OK", "PARTIAL", "FAILED"}:
                raise ValueError(f"{result_key} returned invalid status: {status!r}")
            day_summaries.append(
                {"flow": day_flow, "date": date_text, result_key: ingest_summary, "status": status}
            )
        except Exception as exc:
            errors.append({"date": date_text, "error": str(exc)})
            day_summaries.append(_failure_day(day_flow, date_text, exc))
    return _base_range_summary(
        flow=flow,
        date_range=date_range,
        requested_symbols=requested_symbols,
        day_summaries=day_summaries,
        errors=errors,
    )


def run_daily_backfill_pipeline(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run stock-only DailyStockPrice ingest for each weekday in a date range."""
    date_range = _resolve_range(from_date, to_date)
    requested_symbols = normalize_symbol_scope(symbols)
    return _run_ingest_backfill(
        flow="backfill-daily",
        day_flow="backfill-daily-day",
        date_range=date_range,
        requested_symbols=requested_symbols,
        ingest=run_daily_ingest,
        result_key="daily_summary",
    )


def run_intraday_backfill_pipeline(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run only 1m intraday ingest for each weekday in an inclusive range."""
    date_range = _resolve_range(from_date, to_date)
    requested_symbols = normalize_symbol_scope(symbols)
    return _run_ingest_backfill(
        flow="backfill-intraday",
        day_flow="backfill-intraday-day",
        date_range=date_range,
        requested_symbols=requested_symbols,
        ingest=run_intraday_ingest,
        result_key="intraday_summary",
    )


def _branch_ingest(day_summary: dict[str, Any] | None, key: str) -> dict[str, Any]:
    if not day_summary:
        return {"status": "FAILED", "symbol_count": 0, "error_count": 1, "errors": ["missing branch day summary"]}
    value = day_summary.get(key)
    if isinstance(value, dict):
        return value
    return {
        "status": "FAILED",
        "symbol_count": 0,
        "error_count": 1,
        "errors": [day_summary.get("error") or f"missing {key}"],
    }


def run_backfill_pipeline(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run stock daily, stock intraday, then stock completeness for each date."""
    date_range = _resolve_range(from_date, to_date)
    requested_symbols = normalize_symbol_scope(symbols)

    daily_backfill = run_daily_backfill_pipeline(date_range.from_date, date_range.to_date, requested_symbols)
    intraday_backfill = run_intraday_backfill_pipeline(date_range.from_date, date_range.to_date, requested_symbols)
    daily_by_date = {item["date"]: item for item in daily_backfill["day_summaries"]}
    intraday_by_date = {item["date"]: item for item in intraday_backfill["day_summaries"]}
    day_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = [
        {**error, "branch": "daily"} for error in daily_backfill.get("errors", [])
    ] + [
        {**error, "branch": "intraday"} for error in intraday_backfill.get("errors", [])
    ]

    for date_text in date_range.eligible_dates:
        daily_summary = _branch_ingest(daily_by_date.get(date_text), "daily_summary")
        intraday_summary = _branch_ingest(intraday_by_date.get(date_text), "intraday_summary")
        try:
            ingest_summary = check_ingest(date_text, symbols=requested_symbols)
            failures = _validate_pipeline_summary(daily_summary, "daily ingest")
            failures += _validate_pipeline_summary(intraday_summary, "intraday ingest")
            warnings: list[str] = []
            if daily_summary.get("status") == "PARTIAL":
                warnings.append("daily ingest is partial")
            if intraday_summary.get("status") == "PARTIAL":
                warnings.append("intraday ingest is partial")
            status = _status_from_ingest(ingest_summary, failures, warnings)
            if status == "OK" and warnings:
                status = "PARTIAL"
            day_summaries.append({
                "flow": "backfill-day",
                "date": date_text,
                "daily_summary": daily_summary,
                "intraday_summary": intraday_summary,
                "ingest_summary": ingest_summary,
                "status": status,
                "failures": failures,
                "warnings": warnings,
            })
        except Exception as exc:
            errors.append({"date": date_text, "branch": "completeness", "error": str(exc)})
            failed = _failure_day("backfill-day", date_text, exc)
            failed.update({
                "daily_summary": daily_summary,
                "intraday_summary": intraday_summary,
                "ingest_summary": None,
                "failures": [f"completeness check failed: {exc}"],
                "warnings": [],
            })
            day_summaries.append(failed)

    resolved_symbols = daily_backfill.get("symbols") or intraday_backfill.get("symbols")
    summary = _base_range_summary(
        flow="backfill",
        date_range=date_range,
        requested_symbols=requested_symbols,
        resolved_symbols=resolved_symbols,
        day_summaries=day_summaries,
        errors=errors,
    )
    summary["daily_backfill_summary"] = daily_backfill
    summary["intraday_backfill_summary"] = intraday_backfill
    return summary


def backfill(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None,
    allow_future: bool = False,
) -> dict[str, Any]:
    """Deprecated compatibility wrapper; use :func:`run_backfill_pipeline`."""
    warn("backfill() is deprecated; use run_backfill_pipeline()", DeprecationWarning, stacklevel=2)
    if allow_future:
        raise ValueError("future-date backfill is unsupported")

    def normalize(value: str) -> str:
        try:
            return parse_ddmmyyyy(value).ddmmyyyy
        except ValueError:
            return parse_iso_date(value).ddmmyyyy

    return run_backfill_pipeline(normalize(from_date), normalize(to_date), symbols=symbols)


__all__ = [
    "backfill",
    "run_daily_backfill_pipeline",
    "run_intraday_backfill_pipeline",
    "run_backfill_pipeline",
]
