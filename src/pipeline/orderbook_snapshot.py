from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi


def _get_any(data: dict, *keys: str) -> Any:
    lowered = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_level_list(raw: dict) -> list[dict]:
    for key in ("dataList", "data", "items", "levels", "Levels", "OrderBook", "orderbook"):
        value = raw.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def build_orderbook_record(symbol: str, raw: dict | None, snapshot_time: datetime | None = None) -> dict | None:
    if not raw:
        return None
    snapshot_time = snapshot_time or datetime.now(timezone.utc)
    record = {"symbol": symbol.upper(), "time": snapshot_time.isoformat(), "raw": raw}
    levels = _extract_level_list(raw)
    total_bid = 0.0
    total_ask = 0.0
    for i in range(1, 11):
        level_row = levels[i - 1] if i <= len(levels) else raw
        bid_price = _to_float(_get_any(level_row, f"BidPrice{i}", f"Bid{i}", f"bidPrice{i}", "BidPrice", "bidPrice", "Bid"))
        bid_volume = _to_float(_get_any(level_row, f"BidVolume{i}", f"BidVol{i}", f"bidVolume{i}", "BidVolume", "bidVolume", "BidVol"))
        ask_price = _to_float(_get_any(level_row, f"AskPrice{i}", f"Ask{i}", f"askPrice{i}", "AskPrice", "askPrice", "Ask"))
        ask_volume = _to_float(_get_any(level_row, f"AskVolume{i}", f"AskVol{i}", f"askVolume{i}", "AskVolume", "askVolume", "AskVol"))
        record[f"bid_price_{i}"] = bid_price
        record[f"bid_volume_{i}"] = bid_volume
        record[f"ask_price_{i}"] = ask_price
        record[f"ask_volume_{i}"] = ask_volume
        total_bid += bid_volume or 0
        total_ask += ask_volume or 0
    if total_bid == 0 and total_ask == 0:
        return None
    record["total_bid_depth_10"] = total_bid
    record["total_ask_depth_10"] = total_ask
    total = total_bid + total_ask
    record["orderbook_imbalance"] = total_bid / total if total else 0.5
    record["pressure_score"] = (total_bid - total_ask) / total if total else 0
    return record


def snapshot_orderbook(symbols: list[str] | None = None, ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> int:
    ssi = ssi or SSIApi()
    db = db or SupabaseClient()
    symbols = symbols or db.get_symbols()
    now = datetime.now(timezone.utc)
    records = []
    unsupported = 0
    for symbol in symbols:
        raw = ssi.get_orderbook_snapshot(symbol)
        if raw is None:
            unsupported += 1
            print(f"  ⚠️ {symbol}: unsupported/missing endpoint or no orderbook data")
            continue
        record = build_orderbook_record(symbol, raw, now)
        if record:
            records.append(record)
        else:
            print(f"  ⚠️ {symbol}: orderbook response could not be mapped")
    if records:
        db.upsert_orderbook(records)
    print(f"📚 orderbook_snapshot upserted: {len(records)}; missing/unsupported: {unsupported}")
    return len(records)
