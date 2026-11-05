"""Stock-only EOD source-data backfill; no completeness or downstream stages."""
from __future__ import annotations

from typing import Any, Callable
from src.providers.ssi.registry import resolve_source
from src.ingest.stock_daily.daily import run_daily_ingest
from src.ingest.shared.symbol_scope import normalize_symbol_scope
from src.ingest.shared.backfill_range import (
    _BackfillRange, _resolve_range, _base_range_summary, _failure_day,
)


def _run_ingest_backfill(
    *,
    flow: str,
    day_flow: str,
    date_range: _BackfillRange,
    requested_symbols: list[str] | None,
    ingest: Callable[..., dict[str, Any]],
    result_key: str,
    data_source: str | None = None,
) -> dict[str, Any]:
    day_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for date_text in date_range.eligible_dates:
        try:
            kwargs = {"data_source": data_source} if data_source is not None else {}
            ingest_summary = ingest(date_text, symbols=requested_symbols, **kwargs)
            status = ingest_summary.get("status") if isinstance(ingest_summary, dict) else None
            if status not in {"OK", "PARTIAL", "FAILED"}:
                raise ValueError(f"{result_key} returned invalid status: {status!r}")
            if result_key == 'daily_summary':
                for error in ingest_summary.get('errors', []):
                    errors.append({'date': date_text, **(error if isinstance(error, dict) else {'error': str(error)})})
                if status == 'FAILED' and not ingest_summary.get('errors'):
                    errors.append({'date': date_text, 'error': 'daily ingest returned FAILED without error details'})
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
    symbols: list[str] | tuple[str, ...] | None = None, data_source: str | None = None,
) -> dict[str, Any]:
    """Run stock-only stock daily ingest for each weekday in a date range."""
    resolve_source("stock_daily", data_source)
    date_range = _resolve_range(from_date, to_date)
    requested_symbols = normalize_symbol_scope(symbols)
    result = _run_ingest_backfill(
        flow="backfill-daily",
        day_flow="backfill-daily-day",
        date_range=date_range,
        requested_symbols=requested_symbols,
        ingest=run_daily_ingest,
        result_key="daily_summary",
        data_source=data_source,
    )

    for key in ('valid_clean_writes','partial_clean_writes','rejected_records','mapping_failures','persistence_failures','validation_issues'):
        result[key] = sum((day.get('daily_summary') or {}).get(key,0) for day in result['day_summaries'])
    return result
