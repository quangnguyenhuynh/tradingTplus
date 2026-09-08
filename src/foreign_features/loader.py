"""Paginated, filtered stock_daily loader."""
from __future__ import annotations
from typing import Any

PAGE_SIZE = 1000
COLUMNS = "symbol,trading_date,foreign_buy_vol_total,foreign_sell_vol_total,net_foreign_vol,foreign_buy_val_total,foreign_sell_val_total,net_foreign_val,total_traded_value"


def _paged_stock_daily(db: Any, columns: str, symbols: list[str] | None = None, *, start: str | None = None, end: str | None = None) -> list[dict]:
    rows: list[dict] = []
    for offset in range(0, 10_000_000, PAGE_SIZE):
        query = db.client.table("stock_daily").select(columns)
        if symbols:
            query = query.in_("symbol", symbols)
        if start is not None:
            query = query.gte("trading_date", start)
        if end is not None:
            query = query.lte("trading_date", end)
        query = query.order("trading_date").order("symbol").range(offset, offset + PAGE_SIZE - 1)
        result = db._with_retry(
            lambda query=query: query.execute(),
            action_name=f"load stock_daily {columns} {start or '..'}..{end or '..'} [{offset}]",
        )
        page = result.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
    return rows


def load_session_dates(db: Any, symbols: list[str] | None = None, *, start: str | None = None, end: str | None = None) -> tuple[str, ...]:
    rows = _paged_stock_daily(db, "trading_date", symbols, start=start, end=end)
    return tuple(sorted({str(row["trading_date"]) for row in rows if row.get("trading_date") is not None}))


def load_rows(db: Any, symbols: list[str], start: str, end: str) -> list[dict]:
    return _paged_stock_daily(db, COLUMNS, symbols, start=start, end=end)
