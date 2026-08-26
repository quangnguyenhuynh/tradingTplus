"""Database boundary for index features; no stock feature table is referenced."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.database.client import SupabaseClient

PAGE_SIZE = 1000
WARMUP_SESSIONS = 250


def _execute(db: Any, query: Any, action: str):
    return db._with_retry(lambda: query.execute(), action_name=action)


def _page(query_factory, db: Any, action: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        result = _execute(db, query_factory().range(offset, offset + PAGE_SIZE - 1), action)
        page = result.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def fetch_index_daily_context(db: SupabaseClient, index_code: str, start: str, end: str) -> list[dict]:
    columns = ",".join((
        "index_code", "trading_date", "index_value", "total_vol", "total_val",
        "total_match_vol", "total_match_val", "total_deal_vol", "total_deal_val",
        "advances", "no_changes", "declines", "ceilings", "floors",
    ))
    prior_query = (db.client.table("index_daily").select(columns)
                   .eq("index_code", index_code).lt("trading_date", start)
                   .order("trading_date", desc=True).limit(WARMUP_SESSIONS))
    prior = list(reversed((_execute(db, prior_query, f"load index feature warm-up {index_code}").data or [])))

    def requested_query():
        return (db.client.table("index_daily").select(columns).eq("index_code", index_code)
                .gte("trading_date", start).lte("trading_date", end).order("trading_date"))
    requested = _page(requested_query, db, f"load index_daily {index_code} {start}..{end}")
    return prior + requested


def frame_to_records(frame: pd.DataFrame) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    records: list[dict] = []
    for raw in frame.to_dict("records"):
        row: dict[str, Any] = {"created_at": now, "updated_at": now}
        for key, value in raw.items():
            if key == "trading_date":
                row[key] = pd.Timestamp(value).date().isoformat()
            elif pd.isna(value):
                row[key] = None
            elif hasattr(value, "item"):
                row[key] = value.item()
            else:
                row[key] = value
        records.append(row)
    return records


def upsert_index_features(db: SupabaseClient, records: list[dict]) -> None:
    if records:
        db.upsert_index_features_daily(records)
