from __future__ import annotations

from pprint import pformat
from typing import Any

from src.pipeline.daily import daily_run
from src.pipeline.date_utils import latest_weekday_on_or_before, parse_ddmmyyyy
from src.pipeline.ingest_check import check_ingest

DEFAULT_EOD_TIMEFRAMES = ("1m", "5m", "15m", "60m", "1d")  # compatibility constant; EOD no longer uses it.


def _resolve_eod_date(date: str | None) -> str:
    if date is None or not str(date).strip():
        resolved = latest_weekday_on_or_before().strftime("%d/%m/%Y")
        print(f"📆 EOD date defaulted to latest weekday on/before today (VN): {resolved}")
        return resolved
    return parse_ddmmyyyy(date.strip()).ddmmyyyy


def _validate_fetch_summary(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return []
    symbol_count = int(summary.get("symbol_count") or 0)
    error_count = int(summary.get("error_count") or len(summary.get("errors") or []))
    if symbol_count > 0 and error_count >= max(1, symbol_count):
        return [f"daily_run failed for all symbols ({error_count}/{symbol_count})"]
    return []


def _status_from_ingest(summary: dict[str, Any], failures: list[str], warnings: list[str]) -> str:
    ingest_status = summary.get("status")
    if int(summary.get("stock_daily_count") or 0) == 0:
        failures.append("stock_daily_count == 0")
    if int(summary.get("stock_intraday_count") or 0) == 0:
        failures.append("stock_intraday_count == 0")
    if ingest_status == "FAILED" and "ingest completeness status FAILED" not in failures:
        failures.append("ingest completeness status FAILED")
    if failures:
        return "FAILED"
    if ingest_status == "PARTIAL" or summary.get("missing_stock_daily_count", 0) or summary.get("missing_intraday_count", 0) or summary.get("incomplete_intraday_count", 0):
        warnings.append("ingest completeness is partial")
        return "PARTIAL"
    return "OK"


def run_eod_pipeline(
    date: str | None = None,
    *,
    timeframes: list[str] | tuple[str, ...] | None = None,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """Run EOD ingest and completeness validation only; features are explicit."""
    if timeframes or symbols:
        print("⚠️ EOD ignores symbols/timeframes; run `python main.py features ...` explicitly for features.")
    eod_date = _resolve_eod_date(date)
    print(f"🚀 EOD date: {eod_date}")
    print("1️⃣ Fetch SSI REST data...")
    daily_summary = daily_run(eod_date)
    print(f"✅ Fetch completed for {eod_date}")

    print("2️⃣ Check ingest completeness...")
    ingest_summary = check_ingest(eod_date)
    print("🔎 Ingest check summary:")
    print(pformat(ingest_summary, sort_dicts=True))

    failures = _validate_fetch_summary(daily_summary)
    warnings: list[str] = []
    status = _status_from_ingest(ingest_summary, failures, warnings)
    result = {
        "flow": "eod",
        "date": eod_date,
        "daily_summary": daily_summary,
        "ingest_summary": ingest_summary,
        "status": status,
        "failures": failures,
        "warnings": warnings,
    }
    print(f"{'✅' if status == 'OK' else '⚠️' if status == 'PARTIAL' else '❌'} Final status {status}")
    return result
