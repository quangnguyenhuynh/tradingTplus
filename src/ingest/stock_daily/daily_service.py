"""One-symbol daily fetch -> map -> validate -> persist service."""
import logging
from typing import Any

from src.database.client import SupabaseClient
from src.ingest.stock_daily.daily_fetcher import fetch_daily_price
from src.ingest.stock_daily.daily_mapper import build_raw_daily_record, map_stock_daily_record
from src.ingest.stock_daily.daily_persistence import persist_raw_daily, persist_stock_daily
from src.quality.validators.daily_validator import validate_daily_record
from src.quality.validators.logging_utils import log_validation_result
from src.providers.ssi.base import DataSourceAdapter

logger = logging.getLogger(__name__)


def fetch_daily_for_symbol_with_clients(ssi: DataSourceAdapter, db: SupabaseClient, symbol: str, date: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"symbol": symbol, "date": date, "daily_valid": False, "daily_rows": 0, "daily_errors": 0, "daily_warnings": 0, "status": "FAILED", "error_type": None, "errors": []}
    try:
        adapted = fetch_daily_price(ssi, symbol, date)
        daily = adapted.raw[0] if adapted.raw else None
    except Exception as exc:
        summary.update(error_type="API_ERROR", errors=[str(exc)])
        logger.exception("%s %s: stock daily API_ERROR", symbol, date)
        return summary
    if not daily:
        message = f"{symbol}: không có dữ liệu ngày {date}"
        logger.warning(message)
        summary["error_type"] = "NO_DATA"
        summary["errors"].append(message)
        return summary
    source_id = adapted.source
    raw_payloads = adapted.raw
    for payload in raw_payloads:
        persist_raw_daily(db, build_raw_daily_record(symbol, date, payload, source=source_id))
    summary["daily_payload"] = daily
    clean = adapted.clean[0] if adapted.clean else None
    mapping_report = adapted.mapping_report
    summary["mapping_report"] = mapping_report
    if clean is not None:
        clean = {**clean, "source": source_id}
    validation = validate_daily_record(clean) if clean else None
    if validation:
        summary.update(daily_valid=validation.is_valid, daily_errors=len(validation.errors), daily_warnings=len(validation.warnings))
        log_validation_result(validation, "stock_daily", {"symbol": symbol, "trading_date": clean.get("trading_date")})
    if clean and validation and validation.is_valid:
        persist_stock_daily(db, clean)
        summary.update(daily_rows=1, status="OK")
    else:
        summary["error_type"] = "MISMATCH"
        if adapted is not None:
            summary["errors"].extend(str(error) for error in adapted.validation_errors)
        summary["errors"].append(f"{symbol} {date}: daily validation failed")
    return summary
