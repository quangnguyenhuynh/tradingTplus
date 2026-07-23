"""One-symbol daily fetch -> map -> validate -> persist service."""
import logging
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.daily_fetcher import fetch_daily_price
from src.pipeline.daily_mapper import build_raw_daily_record, build_stock_daily_record
from src.pipeline.daily_persistence import persist_raw_daily, persist_stock_daily
from src.ssi.api import (
    SSIApi,
    SSIDataMismatchError,
    SSIEmptyResponseError,
    SSIResponseError,
)
from src.validation.daily_validator import validate_daily_record
from src.validation.logging_utils import log_validation_result

logger = logging.getLogger(__name__)


def fetch_daily_for_symbol_with_clients(ssi: SSIApi, db: SupabaseClient, symbol: str, date: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"symbol": symbol, "date": date, "daily_valid": False, "daily_rows": 0, "daily_errors": 0, "daily_warnings": 0, "status": "FAILED", "errors": []}
    try:
        daily = fetch_daily_price(ssi, symbol, date)
    except SSIDataMismatchError as exc:
        message = f"{symbol} {date}: MISMATCH: {exc}"
        logger.error(message)
        summary["errors"].append(message)
        summary["failure_type"] = "MISMATCH"
        return summary
    except SSIEmptyResponseError as exc:
        message = f"{symbol} {date}: EMPTY_RESPONSE: {exc}"
        logger.error(message)
        summary["errors"].append(message)
        summary["failure_type"] = "EMPTY_RESPONSE"
        return summary
    except (SSIResponseError, ValueError, OSError) as exc:
        message = f"{symbol} {date}: API_ERROR: {exc}"
        logger.error(message)
        summary["errors"].append(message)
        summary["failure_type"] = "API_ERROR"
        return summary
    if not daily:
        message = f"{symbol} {date}: NO_DATA: SSI trả thành công nhưng không có bản ghi"
        logger.warning(message)
        summary["errors"].append(message)
        summary["failure_type"] = "NO_DATA"
        return summary
    summary["daily_payload"] = daily
    persist_raw_daily(db, build_raw_daily_record(symbol, date, daily))
    clean = build_stock_daily_record(symbol, date, daily)
    validation = validate_daily_record(clean) if clean else None
    if validation:
        summary.update(daily_valid=validation.is_valid, daily_errors=len(validation.errors), daily_warnings=len(validation.warnings))
        log_validation_result(validation, "stock_daily", {"symbol": symbol, "trading_date": clean.get("trading_date")})
    if clean and validation and validation.is_valid:
        persist_stock_daily(db, clean)
        summary.update(daily_rows=1, status="OK")
    else:
        summary["errors"].append(f"{symbol} {date}: daily validation failed")
    return summary
