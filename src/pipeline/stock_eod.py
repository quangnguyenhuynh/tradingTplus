from __future__ import annotations

from pprint import pformat

from src.database.client import SupabaseClient
from src.pipeline.daily import daily_run
from src.pipeline.date_utils import latest_weekday_on_or_before, parse_ddmmyyyy
from src.pipeline.ingest_check import check_ingest
from src.pipeline.intraday_ingest import run_intraday_ingest
from src.pipeline.pipeline_status import status_from_ingest, validate_pipeline_summary
from src.pipeline.symbol_scope import resolve_active_symbol_scope, symbol_scope_summary


def _resolve_stock_eod_date(date: str | None) -> str:
    if date is None or not str(date).strip():
        resolved = latest_weekday_on_or_before().strftime("%d/%m/%Y")
        print(f"📆 Stock EOD date defaulted to latest weekday on/before today (VN): {resolved}")
        return resolved
    return parse_ddmmyyyy(date.strip()).ddmmyyyy


def run_stock_eod_pipeline(
    date: str | None = None,
    *,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """Run stock daily/intraday ingest and stock completeness only."""
    stock_eod_date = _resolve_stock_eod_date(date)
    resolved_symbols, requested_symbols, ignored_symbols = resolve_active_symbol_scope(SupabaseClient(), symbols)
    if ignored_symbols:
        print(f"⚠️ Ignored inactive or unknown symbols: {', '.join(ignored_symbols)}")
    print(f"🚀 Stock EOD date: {stock_eod_date}")
    if not resolved_symbols:
        failure = "no active symbols resolved"
        print(f"❌ {failure}")
        return {
            "flow": "stock-eod", "date": stock_eod_date,
            **symbol_scope_summary(resolved_symbols, requested_symbols),
            "ignored_symbols": ignored_symbols, "daily_summary": None,
            "intraday_summary": None, "ingest_summary": None,
            "status": "FAILED", "failures": [failure], "warnings": [],
        }

    print("1️⃣ Run stock daily ingest...")
    daily_summary = daily_run(stock_eod_date, symbols=resolved_symbols)
    print("2️⃣ Run stock intraday ingest...")
    intraday_summary = run_intraday_ingest(stock_eod_date, symbols=resolved_symbols)
    print("3️⃣ Check stock ingest completeness...")
    ingest_summary = check_ingest(stock_eod_date, symbols=resolved_symbols)
    print(pformat(ingest_summary, sort_dicts=True))

    failures = validate_pipeline_summary(daily_summary, "daily ingest")
    failures += validate_pipeline_summary(intraday_summary, "intraday ingest")
    warnings: list[str] = []
    status = status_from_ingest(ingest_summary, failures, warnings)
    result = {
        "flow": "stock-eod",
        "date": stock_eod_date,
        **symbol_scope_summary(resolved_symbols, requested_symbols),
        "ignored_symbols": ignored_symbols,
        "daily_summary": daily_summary,
        "intraday_summary": intraday_summary,
        "ingest_summary": ingest_summary,
        "status": status,
        "failures": failures,
        "warnings": warnings,
    }
    print(f"{'✅' if status == 'OK' else '⚠️' if status == 'PARTIAL' else '❌'} Final stock-eod status {status}")
    return result
