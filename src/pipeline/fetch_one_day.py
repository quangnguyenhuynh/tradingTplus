"""Backward-compatible one-symbol/day entrypoints.

Implementation lives in the independent daily and intraday pipeline layers. New
code should import the relevant mapper, fetcher, persistence, or service module.
"""
from src.database.client import SupabaseClient
from src.pipeline.daily_fetcher import fetch_daily_price
from src.pipeline.daily_mapper import build_raw_daily_record, build_stock_daily_record, payload_matches_request
from src.pipeline.daily_service import fetch_daily_for_symbol_with_clients
from src.pipeline.intraday_fetcher import fetch_intraday_candles
from src.pipeline.intraday_mapper import build_intraday_records, parse_time
from src.pipeline.intraday_persistence import save_intraday_records
from src.pipeline.intraday_service import fetch_intraday_for_symbol_with_clients
from src.pipeline.date_utils import trading_date_iso
from src.ssi.api import SSIApi


def fetch_one_day_with_clients(ssi: SSIApi, db: SupabaseClient, symbol: str, date: str) -> int:
    """Compatibility orchestration for one symbol/date; prefer separate services."""
    daily_summary = fetch_daily_for_symbol_with_clients(ssi, db, symbol, date)
    if daily_summary.get("status") != "OK":
        return 0
    context = db.get_stock_daily(symbol, trading_date_iso(date)) if hasattr(db, "get_stock_daily") else None
    intraday_summary = fetch_intraday_for_symbol_with_clients(ssi, db, symbol, date, daily_context=context)
    return int(intraday_summary.get("candles_valid") or 0)


def fetch_one_day(symbol: str, date: str) -> int:
    """Compatibility write entrypoint for one explicitly scoped symbol/date."""
    return fetch_one_day_with_clients(SSIApi(), SupabaseClient(), symbol, date)


__all__ = [
    "build_intraday_records", "build_raw_daily_record", "build_stock_daily_record",
    "fetch_daily_for_symbol_with_clients", "fetch_daily_price", "fetch_intraday_candles",
    "fetch_intraday_for_symbol_with_clients", "fetch_one_day", "fetch_one_day_with_clients",
    "parse_time", "payload_matches_request", "save_intraday_records",
]
