"""Bounded persistence for the dedicated derived table."""
from __future__ import annotations
from typing import Any
from src.utils.time_utils import app_now_iso


def upsert(db: Any, rows: list[dict]) -> None:
    stamp = app_now_iso()
    prepared = [{**row, "updated_at": stamp} for row in rows]
    db._upsert_in_batches("stock_foreign_features_daily", prepared, on_conflict="symbol,trading_date", batch_size=500)


def load_existing(db: Any, symbols: list[str], start: str, end: str) -> list[dict]:
    result = db._with_retry(lambda: db.client.table("stock_foreign_features_daily").select("symbol,trading_date,formula_version,source_fingerprint,quality_status,created_at").in_("symbol", symbols).gte("trading_date", start).lte("trading_date", end).execute(), action_name="load existing foreign features")
    return result.data or []
