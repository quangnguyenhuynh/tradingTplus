"""One-symbol daily fetch -> map -> validate -> persist service."""
import logging
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.daily_fetcher import fetch_daily_price
from src.pipeline.daily_mapper import build_raw_daily_record, build_stock_daily_record
from src.pipeline.daily_persistence import persist_raw_daily, persist_stock_daily
from src.ssi.api import SSIApi
from src.ssi.api import SSIDataMismatchError, SSIEmptyResponseError
from src.validation.daily_validator import validate_daily_record
from src.validation.logging_utils import log_validation_result

logger = logging.getLogger(__name__)


def fetch_daily_for_symbol_with_clients(ssi: SSIApi, db: SupabaseClient, symbol: str, date: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"symbol": symbol, "date": date, "daily_valid": False, "daily_rows": 0, "daily_errors": 0, "daily_warnings": 0, "status": "FAILED", "error_type": None, "errors": []}
    try:
        daily = fetch_daily_price(ssi, symbol, date)
    except SSIEmptyResponseError as exc:
        summary.update(error_type="EMPTY_RESPONSE", errors=[str(exc)])
        logger.error("%s %s: DailyStockPrice EMPTY_RESPONSE", symbol, date)
        return summary
    except SSIDataMismatchError as exc:
        summary.update(error_type="MISMATCH", errors=[str(exc)])
        logger.error("%s %s: DailyStockPrice MISMATCH", symbol, date)
        return summary
    except Exception as exc:
        summary.update(error_type="API_ERROR", errors=[str(exc)])
        logger.exception("%s %s: DailyStockPrice API_ERROR", symbol, date)
        return summary
    if not daily:
        message = f"{symbol}: không có dữ liệu ngày {date}"
        logger.warning(message)
        summary["error_type"] = "NO_DATA"
        summary["errors"].append(message)
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
        summary["error_type"] = "MISMATCH"
        summary["errors"].append(f"{symbol} {date}: daily validation failed")
    return summary
