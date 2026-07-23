"""One-symbol intraday fetch -> map -> validate -> persist service."""
import logging
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.intraday_fetcher import fetch_intraday_candles
from src.pipeline.intraday_mapper import build_intraday_records, daily_context_payload, deduplicate_intraday_records
from src.pipeline.intraday_persistence import persist_raw_intraday, persist_stock_intraday
from src.ssi.api import SSIApi
from src.ssi.api import SSIEmptyResponseError
from src.validation.intraday_validator import validate_intraday_batch, validate_intraday_record
from src.validation.logging_utils import log_validation_result

logger = logging.getLogger(__name__)


def fetch_intraday_for_symbol_with_clients(ssi: SSIApi, db: SupabaseClient, symbol: str, date: str, daily_context: dict | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {"symbol": symbol, "date": date, "candles_received": 0, "candles_valid": 0, "candles_rejected": 0, "daily_context_missing": daily_context is None, "batch_errors": 0, "batch_warnings": 0, "status": "FAILED", "error_type": None, "errors": [], "warnings": []}
    try:
        candles = fetch_intraday_candles(ssi, symbol, date)
    except SSIEmptyResponseError as exc:
        summary.update(error_type="EMPTY_RESPONSE", errors=[str(exc)])
        logger.error("%s %s: IntradayOhlc EMPTY_RESPONSE", symbol, date)
        return summary
    except Exception as exc:
        summary.update(error_type="API_ERROR", errors=[str(exc)])
        logger.exception("%s %s: IntradayOhlc API_ERROR", symbol, date)
        return summary
    summary["candles_received"] = len(candles)
    if not candles:
        warning = f"{symbol}: không có dữ liệu intraday"
        logger.warning(warning)
        summary["warnings"].append(warning)
        summary["error_type"] = "NO_DATA"
        return summary
    if daily_context is None:
        warning = f"{symbol} {date}: daily_context_missing"
        logger.warning(warning)
        summary["warnings"].append(warning)
    raw, clean = build_intraday_records(symbol, date, daily_context_payload(daily_context), candles)
    if not clean:
        message = f"{symbol} {date}: intraday payload does not match the requested date/time contract"
        summary.update(error_type="MISMATCH", errors=[message], candles_rejected=len(candles))
        logger.error(message)
        return summary
    persist_raw_intraday(db, raw)
    individually_valid = []
    for record in clean:
        result = validate_intraday_record(record)
        log_validation_result(result, "stock_intraday", {"symbol": symbol, "time": record.get("time")})
        if result.is_valid:
            individually_valid.append(record)
    batch = validate_intraday_batch(individually_valid, daily_record=daily_context)
    log_validation_result(batch, "stock_intraday", {"symbol": symbol, "date": date})
    records_to_save = individually_valid
    if any(issue.code == "INTRADAY_DUPLICATE_TIMESTAMP" for issue in batch.errors):
        records_to_save = deduplicate_intraday_records(individually_valid)
    persist_stock_intraday(db, records_to_save)
    summary.update(candles_valid=len(records_to_save), candles_rejected=len(clean) - len(records_to_save), batch_errors=len(batch.errors), batch_warnings=len(batch.warnings))
    summary["status"] = "OK" if records_to_save and not batch.errors else "PARTIAL" if records_to_save else "FAILED"
    return summary
