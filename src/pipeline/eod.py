from __future__ import annotations

from pprint import pformat
from typing import Any

from src.engine.feature_engine import run_feature_engine
from src.pipeline.daily import daily_run
from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy
from src.pipeline.ingest_check import check_ingest

DEFAULT_EOD_TIMEFRAMES = ("1m", "5m", "15m")


def _resolve_eod_date(date: str | None) -> str:
    if date is None or not str(date).strip():
        resolved = latest_previous_weekday().strftime("%d/%m/%Y")
        print(f"📆 EOD date defaulted to latest previous weekday (VN): {resolved}")
        return resolved
    parsed = parse_ddmmyyyy(date.strip())
    return parsed.ddmmyyyy


def _validate_ingest_summary(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if int(summary.get("stock_daily_count") or 0) == 0:
        failures.append("stock_daily_count == 0")
    if int(summary.get("stock_intraday_count") or 0) == 0:
        failures.append("stock_intraday_count == 0")

    symbol_count = int(summary.get("symbol_count") or 0)
    missing_count = len(summary.get("missing_stock_daily_symbols") or [])
    if symbol_count > 0 and missing_count >= max(1, symbol_count // 2):
        failures.append(
            f"missing stock_daily for too many symbols ({missing_count}/{symbol_count}; first 100 tracked)"
        )
    return failures


def _validate_fetch_summary(summary: Any) -> list[str]:
    if not isinstance(summary, dict):
        return []

    symbol_count = int(summary.get("symbol_count") or 0)
    error_count = int(summary.get("error_count") or len(summary.get("errors") or []))
    if symbol_count > 0 and error_count >= max(1, symbol_count // 2):
        return [f"daily_run failed for too many symbols ({error_count}/{symbol_count})"]
    return []


def run_eod_pipeline(
    date: str | None = None,
    *,
    timeframes: list[str] | tuple[str, ...] | None = None,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict:
    """Run the end-of-day ingest + feature pipeline.

    The EOD task intentionally stops after feature generation. Signal and
    backtest jobs are left for separate workflows.
    """
    eod_date = _resolve_eod_date(date)
    feature_timeframes = tuple(timeframes or DEFAULT_EOD_TIMEFRAMES)
    feature_symbols = list(symbols) if symbols else None

    print(f"🚀 EOD date: {eod_date}")
    print("1️⃣ Fetch SSI REST data...")
    fetch_summary = daily_run(eod_date)
    print(f"✅ Fetch completed for {eod_date}")

    print("2️⃣ Check ingest completeness...")
    ingest_summary = check_ingest(eod_date)
    print("🔎 Ingest check summary:")
    print(pformat(ingest_summary, sort_dicts=True))

    failures = _validate_fetch_summary(fetch_summary)
    failures.extend(_validate_ingest_summary(ingest_summary))
    if failures:
        status = "FAILED"
        result = {
            "date": eod_date,
            "ingest_summary": ingest_summary,
            "feature_records": 0,
            "status": status,
            "failures": failures,
        }
        print(f"❌ Final status {status}: " + "; ".join(failures))
        raise RuntimeError(f"EOD pipeline failed before feature engine: {'; '.join(failures)}")

    print(f"3️⃣ Run feature engine incremental for timeframes={feature_timeframes} symbols={feature_symbols or 'ALL'}...")
    feature_records = run_feature_engine(symbols=feature_symbols, mode="incremental", timeframes=feature_timeframes)
    print(f"✅ Feature records upserted: {feature_records}")

    if int(feature_records or 0) == 0:
        status = "FAILED"
        result = {
            "date": eod_date,
            "ingest_summary": ingest_summary,
            "feature_records": feature_records,
            "status": status,
            "failures": ["feature_records == 0"],
        }
        print(f"❌ Final status {status}: feature_records == 0")
        raise RuntimeError("EOD pipeline failed: feature_records == 0")

    status = "OK"
    result = {
        "date": eod_date,
        "ingest_summary": ingest_summary,
        "feature_records": feature_records,
        "status": status,
    }
    print(f"✅ Final status {status}")
    return result
