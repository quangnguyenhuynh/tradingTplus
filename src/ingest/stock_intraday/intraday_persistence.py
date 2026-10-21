"""Persistence boundary for raw and clean intraday records."""
from src.database.client import SupabaseClient


def persist_raw_intraday(db: SupabaseClient, records: list[dict]) -> None:
    if records:
        db.upsert_raw(records)


def persist_stock_intraday(db: SupabaseClient, records: list[dict]) -> None:
    if records:
        db.upsert_intraday(records)


def save_intraday_records(db: SupabaseClient, raw_records: list[dict], clean_records: list[dict]) -> int:
    """Compatibility persistence helper returning the clean row count."""
    persist_raw_intraday(db, raw_records)
    persist_stock_intraday(db, clean_records)
    return len(clean_records)
