"""Execution estimates from clean, canonical one-minute candles."""

from datetime import datetime


def _dt(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return result


def estimate_entry(candles: list[dict], decision_time: str) -> dict:
    cutoff = _dt(decision_time)
    eligible = [row for row in candles if row.get("timeframe") == "1m" and _dt(row["time"]) > cutoff and row.get("open") is not None and float(row["open"]) > 0]
    if not eligible:
        return {"entry_status": "missing", "entry_time": None, "entry_price": None, "entry_model": "next_1m_open_v1"}
    row = min(eligible, key=lambda value: _dt(value["time"]))
    return {"entry_status": "available", "entry_time": row["time"], "entry_price": float(row["open"]), "entry_model": "next_1m_open_v1"}
