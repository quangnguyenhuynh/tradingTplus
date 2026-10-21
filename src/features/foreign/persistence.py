"""Bounded persistence for the dedicated derived table."""
from __future__ import annotations
from typing import Any
from src.utils.time_utils import app_now_iso

PAGE_SIZE = 1000
METRIC_COLUMNS = (
    "net_value_5d", "net_value_20d", "activity_value_5d", "activity_value_20d",
    "net_value_ratio_5d", "net_value_ratio_20d", "activity_ratio_5d", "activity_ratio_20d",
    "buy_days_5d", "buy_days_20d", "sell_days_5d", "sell_days_20d",
    "net_value_ratio_change_5d", "activity_ratio_change_5d",
)


def upsert(db: Any, rows: list[dict]) -> None:
    if not rows:
        return
    stamp = app_now_iso()
    prepared = [{**{column: None for column in METRIC_COLUMNS}, **row, "updated_at": stamp} for row in rows]
    db._upsert_in_batches("stock_foreign_features_daily", prepared, on_conflict="symbol,trading_date", batch_size=500)


def load_existing(db: Any, symbols: list[str], start: str, end: str) -> list[dict]:
    rows: list[dict] = []
    for offset in range(0, 10_000_000, PAGE_SIZE):
        query = (db.client.table("stock_foreign_features_daily")
            .select("symbol,trading_date,formula_version,source_fingerprint,quality_status,created_at")
            .in_("symbol", symbols).gte("trading_date", start).lte("trading_date", end)
            .order("symbol").order("trading_date").range(offset, offset + PAGE_SIZE - 1))
        result = db._with_retry(lambda query=query: query.execute(), action_name=f"load existing foreign features [{offset}]")
        page = result.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
    raise RuntimeError("pagination safety limit reached: existing foreign features")
