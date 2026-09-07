"""Paginated, filtered stock_daily loader."""
from __future__ import annotations
from typing import Any

PAGE_SIZE = 1000
COLUMNS = "symbol,trading_date,foreign_buy_vol_total,foreign_sell_vol_total,net_foreign_vol,foreign_buy_val_total,foreign_sell_val_total,net_foreign_val,total_traded_value"


def load_rows(db: Any, symbols: list[str], start: str, end: str) -> list[dict]:
    rows: list[dict] = []
    for offset in range(0, 10_000_000, PAGE_SIZE):
        query = db.client.table("stock_daily").select(COLUMNS).in_("symbol", symbols).gte("trading_date", start).lte("trading_date", end).order("trading_date").order("symbol").range(offset, offset + PAGE_SIZE - 1)
        result = db._with_retry(lambda query=query: query.execute(), action_name=f"load foreign source {start}..{end} [{offset}]")
        page = result.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
    return rows
