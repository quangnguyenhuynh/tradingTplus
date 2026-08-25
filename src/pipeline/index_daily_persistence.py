"""Raw and clean index-daily persistence boundaries."""
from datetime import datetime, timezone
from typing import Iterable

from src.database.client import SupabaseClient


def _validate_index_raw_daily_row(row: dict) -> None:
    """Reject an invalid raw audit payload before making a Supabase request."""
    if row.get("created_at") is None:
        raise ValueError(
            "index_raw_daily row missing required created_at: "
            f"index_code={row.get('index_code')}, trading_date={row.get('trading_date')}"
        )
    try:
        parsed = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "index_raw_daily row has invalid created_at: "
            f"index_code={row.get('index_code')}, trading_date={row.get('trading_date')}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            "index_raw_daily row has non-timezone-aware created_at: "
            f"index_code={row.get('index_code')}, trading_date={row.get('trading_date')}"
        )


def persist_index_raw_daily(db: SupabaseClient, records: Iterable[dict]) -> None:
    """Stamp and persist one immutable SSI raw-response batch."""
    ingestion_timestamp = datetime.now(timezone.utc).isoformat()
    rows = []
    for record in records:
        row = dict(record)
        row["created_at"] = ingestion_timestamp
        _validate_index_raw_daily_row(row)
        rows.append(row)
    if rows:
        db.upsert_index_raw_daily(rows)


def persist_index_daily(db: SupabaseClient, record: dict) -> None:
    db.upsert_index_daily([record])
