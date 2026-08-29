from __future__ import annotations

from pprint import pformat

from src.database.client import SupabaseClient
from src.pipeline.date_utils import latest_weekday_on_or_before, parse_ddmmyyyy
from src.pipeline.ingest_check import check_intraday_ingest
from src.pipeline.intraday_ingest import run_intraday_ingest
from src.pipeline.pipeline_status import status_from_intraday_ingest, validate_pipeline_summary
from src.pipeline.symbol_scope import resolve_intraday_symbol_scope, symbol_scope_summary


def _resolve_stock_intraday_date(date: str | None) -> str:
    if date is None or not str(date).strip():
        resolved = latest_weekday_on_or_before().strftime("%d/%m/%Y")
        print(f"📆 Stock intraday date defaulted to latest weekday on/before today (VN): {resolved}")
        return resolved
    return parse_ddmmyyyy(date.strip()).ddmmyyyy


def run_stock_intraday_pipeline(date: str | None = None, *, symbols=None) -> dict:
    """Run automatic-scope SSI IntradayOhlc 1m ingest and completeness only."""
    target_date = _resolve_stock_intraday_date(date)
    resolved, requested, ignored = resolve_intraday_symbol_scope(SupabaseClient(), symbols)
    if ignored:
        print(f"⚠️ Ignored inactive or unknown intraday symbols: {', '.join(ignored)}")
    base = {"flow": "stock-intraday", "date": target_date,
            **symbol_scope_summary(resolved, requested), "ignored_symbols": ignored}
    if not resolved:
        failure = "no effective active intraday symbols resolved"
        return {**base, "ingest_summary": None, "completeness_summary": None,
                "status": "FAILED", "failures": [failure], "warnings": []}

    print("1️⃣ Run stock intraday 1m ingest...")
    ingest = run_intraday_ingest(target_date, symbols=resolved)
    print("2️⃣ Check intraday-only completeness...")
    completeness = check_intraday_ingest(target_date, symbols=resolved)
    print(pformat(completeness, sort_dicts=True))
    failures = validate_pipeline_summary(ingest, "intraday ingest")
    warnings: list[str] = []
    if ingest.get("status") == "PARTIAL":
        warnings.append("intraday ingest is partial")
    status = status_from_intraday_ingest(completeness, failures, warnings)
    if status == "OK" and warnings:
        status = "PARTIAL"
    return {**base, "ingest_summary": ingest, "completeness_summary": completeness,
            "status": status, "failures": failures, "warnings": warnings}
