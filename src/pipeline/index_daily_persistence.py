"""Raw and clean index-daily persistence boundaries."""
from datetime import datetime, timezone

from src.database.client import SupabaseClient


def persist_index_raw_daily(db: SupabaseClient, record: dict) -> None:
    row = dict(record)
    if row.get("created_at") is None:
        row["created_at"] = datetime.now(timezone.utc).isoformat()
    db.upsert_index_raw_daily([row])


def persist_index_daily(db: SupabaseClient, record: dict) -> None:
    db.upsert_index_daily([record])
