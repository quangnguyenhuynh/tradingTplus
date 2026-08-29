from __future__ import annotations

from pprint import pformat

from src.database.client import SupabaseClient
from src.pipeline.daily import daily_run
from src.pipeline.date_utils import latest_weekday_on_or_before, parse_ddmmyyyy
from src.pipeline.ingest_check import check_daily_ingest
from src.pipeline.pipeline_status import status_from_daily_ingest, validate_pipeline_summary
from src.pipeline.symbol_scope import resolve_active_symbol_scope, symbol_scope_summary


def _resolve_stock_eod_date(date: str | None) -> str:
    if date is None or not str(date).strip():
        resolved = latest_weekday_on_or_before().strftime("%d/%m/%Y")
        print(f"📆 Stock EOD date defaulted to latest weekday on/before today (VN): {resolved}")
        return resolved
    return parse_ddmmyyyy(date.strip()).ddmmyyyy


def run_stock_eod_pipeline(date: str | None = None, *, symbols=None) -> dict:
    """Run daily-only stock ingest and daily-only completeness."""
    stock_eod_date = _resolve_stock_eod_date(date)
    resolved, requested, ignored = resolve_active_symbol_scope(SupabaseClient(), symbols)
    if ignored:
        print(f"⚠️ Ignored inactive or unknown symbols: {', '.join(ignored)}")
    if not resolved:
        failure = "no active symbols resolved"
        return {"flow": "stock-eod", "date": stock_eod_date,
                **symbol_scope_summary(resolved, requested), "ignored_symbols": ignored,
                "daily_summary": None, "intraday_summary": None,
                "intraday_summary_deprecated": True, "ingest_summary": None,
                "status": "FAILED", "failures": [failure], "warnings": []}
    print("1️⃣ Run stock daily ingest...")
    daily_summary = daily_run(stock_eod_date, symbols=resolved)
    print("2️⃣ Check daily ingest completeness...")
    completeness = check_daily_ingest(stock_eod_date, symbols=resolved)
    print(pformat(completeness, sort_dicts=True))
    failures = validate_pipeline_summary(daily_summary, "daily ingest")
    warnings: list[str] = []
    status = status_from_daily_ingest(completeness, failures, warnings)
    return {"flow": "stock-eod", "date": stock_eod_date,
            **symbol_scope_summary(resolved, requested), "ignored_symbols": ignored,
            "daily_summary": daily_summary, "intraday_summary": None,
            "intraday_summary_deprecated": True, "ingest_summary": completeness,
            "status": status, "failures": failures, "warnings": warnings}
