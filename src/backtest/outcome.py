"""Holding outcomes indexed by observed trading sessions, never calendar days."""

from datetime import date


HORIZONS = (1, 3, 5)


def map_outcomes(daily_rows: list[dict], entry_session: str | date, entry_price: float | None) -> dict:
    session = date.fromisoformat(str(entry_session)) if not isinstance(entry_session, date) else entry_session
    rows = sorted((row for row in daily_rows if date.fromisoformat(str(row["trading_date"])) > session), key=lambda row: row["trading_date"])
    result = {}
    for horizon in HORIZONS:
        row = rows[horizon - 1] if len(rows) >= horizon else None
        close = row.get("close_price") if row else None
        available = entry_price is not None and close is not None and float(close) > 0
        result[f"h{horizon}_status"] = "available" if available else "missing"
        result[f"h{horizon}_session"] = str(row["trading_date"]) if row else None
        result[f"h{horizon}_close"] = float(close) if close is not None else None
        result[f"h{horizon}_gross_return"] = float(close) / entry_price - 1 if available else None
    return result
