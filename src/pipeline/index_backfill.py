"""Inclusive weekday DailyIndex backfill."""
from __future__ import annotations

from src.pipeline.backfill import _base_range_summary, _failure_day, _resolve_range
from src.pipeline.index_daily import run_index_daily_ingest
from src.pipeline.index_scope import normalize_index_scope
from src.pipeline.date_utils import parse_index_date


def run_index_backfill_pipeline(from_date: str, to_date: str, indexes: list[str] | tuple[str, ...] | None = None) -> dict:
    date_range = _resolve_range(parse_index_date(from_date).ddmmyyyy, parse_index_date(to_date).ddmmyyyy); requested = normalize_index_scope(indexes)
    days = []; errors = []
    for date_text in date_range.eligible_dates:
        try:
            summary = run_index_daily_ingest(date_text, requested)
            days.append({"flow": "index-backfill-day", "date": date_text, "index_daily_summary": summary, "status": summary["status"]})
        except Exception as exc:
            errors.append({"date": date_text, "error": str(exc)}); days.append(_failure_day("index-backfill-day", date_text, exc))
    result = _base_range_summary(flow="index-backfill", date_range=date_range, requested_symbols=requested, day_summaries=days, errors=errors)
    result["index_scope"] = result.pop("symbol_scope"); result["requested_indexes"] = result.pop("requested_symbols"); result["indexes"] = result.pop("symbols"); result["index_count"] = result.pop("symbol_count")
    if result["indexes"] is None:
        for day in days:
            nested = day.get("index_daily_summary") or {}
            if isinstance(nested.get("indexes"), list):
                result["indexes"] = nested["indexes"]
                result["index_count"] = len(nested["indexes"])
                break
    return result
