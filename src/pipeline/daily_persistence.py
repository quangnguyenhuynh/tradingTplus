"""Persistence boundary for daily raw and clean records."""
from src.database.client import SupabaseClient


def persist_raw_daily(db: SupabaseClient, record: dict | None) -> None:
    if record:
        db.upsert_raw_daily([record])


def persist_stock_daily(db: SupabaseClient, record: dict | None) -> None:
    if record:
        db.upsert_stock_daily([record])
