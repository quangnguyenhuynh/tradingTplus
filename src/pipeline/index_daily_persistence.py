"""Raw and clean index-daily persistence boundaries."""
from src.database.client import SupabaseClient


def persist_index_raw_daily(db: SupabaseClient, record: dict) -> None:
    db.upsert_index_raw_daily([record])


def persist_index_daily(db: SupabaseClient, record: dict) -> None:
    db.upsert_index_daily([record])
