"""Historical source-data backfill orchestrated through the production EOD flow."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from warnings import warn

from src.pipeline.date_utils import parse_ddmmyyyy, parse_iso_date, validate_not_future
from src.pipeline.eod import run_eod_pipeline
from src.pipeline.symbol_scope import normalize_symbol_scope


def _range_status(*, processed_days: int, ok_days: int, partial_days: int, failed_days: int) -> str:
    """Aggregate EOD statuses; an empty (weekend-only) range is a successful no-op."""
    if processed_days == 0 or ok_days == processed_days:
        return "OK"
    if failed_days == processed_days:
        return "FAILED"
    if partial_days or ok_days or failed_days:
        return "PARTIAL"
    return "FAILED"


def run_backfill_pipeline(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run the EOD pipeline once per weekday in an inclusive DD/MM/YYYY range."""
    start = parse_ddmmyyyy(from_date)
    end = parse_ddmmyyyy(to_date)
    validate_not_future(start)
    validate_not_future(end)
    if start.date > end.date:
        raise ValueError("from_date must be <= to_date")
    requested_symbols = normalize_symbol_scope(symbols)

    requested_calendar_days = (end.date - start.date).days + 1
    skipped_weekend_dates: list[str] = []
    day_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    counts = {"OK": 0, "PARTIAL": 0, "FAILED": 0}

    current = start.date
    while current <= end.date:
        date_text = current.strftime("%d/%m/%Y")
        if current.weekday() >= 5:
            skipped_weekend_dates.append(date_text)
            current += timedelta(days=1)
            continue

        try:
            summary = run_eod_pipeline(date_text, symbols=requested_symbols)
            status = summary.get("status") if isinstance(summary, dict) else None
            if status not in counts:
                raise ValueError(f"EOD returned invalid status: {status!r}")
            day_summaries.append(summary)
            counts[status] += 1
        except Exception as exc:
            message = str(exc)
            error = {"date": date_text, "error": message}
            errors.append(error)
            day_summaries.append({"flow": "eod", "date": date_text, "status": "FAILED", "error": message})
            counts["FAILED"] += 1
        current += timedelta(days=1)

    processed_days = len(day_summaries)
    resolved_symbols = requested_symbols
    if resolved_symbols is None and day_summaries:
        resolved_symbols = day_summaries[0].get("symbols")
    return {
        "flow": "backfill",
        "from_date": start.ddmmyyyy,
        "to_date": end.ddmmyyyy,
        "symbol_scope": "EXPLICIT" if requested_symbols is not None else "ALL_ACTIVE",
        "requested_symbols": requested_symbols,
        "symbols": resolved_symbols,
        "symbol_count": len(resolved_symbols) if resolved_symbols is not None else 0,
        "requested_calendar_days": requested_calendar_days,
        "processed_days": processed_days,
        "skipped_weekend_days": len(skipped_weekend_dates),
        "skipped_weekend_dates": skipped_weekend_dates,
        "ok_days": counts["OK"],
        "partial_days": counts["PARTIAL"],
        "failed_days": counts["FAILED"],
        "error_count": len(errors),
        "errors": errors,
        "day_summaries": day_summaries,
        "status": _range_status(
            processed_days=processed_days,
            ok_days=counts["OK"],
            partial_days=counts["PARTIAL"],
            failed_days=counts["FAILED"],
        ),
    }


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


__all__ = ["backfill", "run_backfill_pipeline"]
