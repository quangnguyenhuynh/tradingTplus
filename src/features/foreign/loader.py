"""Paginated, deterministically ordered stock_daily loader."""
from __future__ import annotations
from typing import Any

PAGE_SIZE = 1000
COLUMNS = "symbol,trading_date,foreign_buy_vol_total,foreign_sell_vol_total,net_foreign_vol,foreign_buy_val_total,foreign_sell_val_total,net_foreign_val,total_traded_value"


def _execute_pages(db: Any, query_factory, action: str) -> list[dict]:
    rows: list[dict] = []
    for offset in range(0, 10_000_000, PAGE_SIZE):
        query = query_factory().range(offset, offset + PAGE_SIZE - 1)
        result = db._with_retry(
            lambda query=query: query.execute(), action_name=f"{action} [{offset}]"
        )
        page = result.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
    raise RuntimeError(f"pagination safety limit reached: {action}")


def load_rows(db: Any, symbols: list[str], start: str, end: str, warmup_rows: int = 19) -> list[dict]:
    """Load the requested range plus at most warmup_rows before start per symbol."""
    if not symbols:
        return []
    in_range = _execute_pages(
        db,
        lambda: db.client.table("stock_daily").select(COLUMNS).in_("symbol", symbols)
        .gte("trading_date", start).lte("trading_date", end)
        .order("symbol").order("trading_date"),
        f"load foreign source {start}..{end}",
    )
    warmup: list[dict] = []
    if warmup_rows:
        for symbol in symbols:
            query = (
                db.client.table("stock_daily").select(COLUMNS).eq("symbol", symbol)
                .lt("trading_date", start).order("trading_date", desc=True).limit(warmup_rows)
            )
            result = db._with_retry(
                lambda query=query: query.execute(), action_name=f"load foreign warmup {symbol} before {start}"
            )
            warmup.extend(result.data or [])
    return sorted(warmup + in_range, key=lambda row: (str(row["symbol"]), str(row["trading_date"])))


def load_following_dates(db: Any, symbols: list[str], end: str, count: int = 19) -> dict[str, list[str]]:
    """Return the next source-row dates per symbol without writing them."""
    following: dict[str, list[str]] = {}
    for symbol in symbols:
        query = (
            db.client.table("stock_daily").select("symbol,trading_date").eq("symbol", symbol)
            .gt("trading_date", end).order("trading_date").limit(count)
        )
        result = db._with_retry(
            lambda query=query: query.execute(), action_name=f"load affected foreign dates {symbol} after {end}"
        )
        following[symbol] = [str(row["trading_date"]) for row in (result.data or [])]
    return following
