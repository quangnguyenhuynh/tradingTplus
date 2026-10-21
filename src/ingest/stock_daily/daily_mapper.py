"""Daily raw evidence and verified v3 mapping helpers over the shared mapping engine."""
import hashlib
import json

from src.contracts import map_record
from src.ingest.shared.date_utils import trading_date_iso


def map_stock_daily_record(symbol: str, date: str, daily: dict):
    """Map only verified v3 securitiesSummary payloads; no source fallback."""
    result = map_record("ssi_v3", "stock_daily", {f"summary.{key}": value for key, value in daily.items()}, {})
    candidate = dict(result.candidate) if result.candidate is not None else None
    report = result.report
    if candidate is not None:
        from src.contracts.derived import apply_derived_fields
        apply_derived_fields("stock_daily", candidate)
        if candidate["symbol"] != symbol.upper() or candidate["trading_date"] != trading_date_iso(date):
            candidate = None
            report = {**report, "records_valid": 0, "records_rejected": 1,
                      "errors": report["errors"] + [{"code": "REQUEST_SCOPE_MISMATCH"}]}
        else:
            candidate["raw"] = daily
    return candidate, report


def build_stock_daily_record(symbol: str, date: str, daily: dict) -> dict | None:
    return map_stock_daily_record(symbol, date, daily)[0]

def build_raw_daily_record(symbol: str, date: str, daily: dict, source: str = "ssi_v3") -> dict | None:
    requested_date = trading_date_iso(date)
    if not requested_date: return None
    return {"symbol": symbol, "trading_date": requested_date, "source": source, "data_hash": hashlib.sha256(json.dumps(daily, sort_keys=True).encode()).hexdigest(), "payload": daily}
