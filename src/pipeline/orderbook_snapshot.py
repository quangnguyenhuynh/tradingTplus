from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.ssi.streaming import SSIStreamingQuoteClient
from src.config import config


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
    """Map SSI quote/marketdata depth payloads into orderbook_snapshot rows.

    Supports FCData quote fields such as BidPrice1/BidVol1 and AskPrice1/AskVol1
    from the market data stream, plus common REST/list-shaped variants.
    """
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
        record[f"bid_vol_{i}"] = bid_volume
        record[f"ask_price_{i}"] = ask_price
        record[f"ask_vol_{i}"] = ask_volume
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


def snapshot_orderbook_from_stream(
    symbols: list[str] | None = None,
    timeout_sec: int | None = None,
    db: SupabaseClient | None = None,
    debug: bool = False,
) -> int:
    timeout_sec = timeout_sec or config.ORDERBOOK_SNAPSHOT_TIMEOUT_SEC
    if not config.SSI_STREAMING_ENABLED:
        print("⚠️ SSI_STREAMING_ENABLED=false; streaming quote snapshot is disabled")
        return 0
    if not config.SSI_STREAMING_URL:
        print("⚠️ SSI_STREAMING_URL chưa cấu hình, không thể lấy orderbook snapshot từ official REST")
        return 0
    db = db or SupabaseClient()
    symbols = [symbol.upper() for symbol in (symbols or db.get_symbols())]
    if not symbols:
        print("⚠️ No symbols available for orderbook snapshot")
        return 0
    client = SSIStreamingQuoteClient(timeout_sec=timeout_sec)
    try:
        client.connect()
        client.subscribe_quote(symbols if symbols else "ALL")
        latest = client.collect_latest_quotes(symbols, timeout_sec=timeout_sec, debug=debug)
    except Exception as exc:
        print(f"⚠️ {exc}")
        return 0
    finally:
        client.close()

    now = datetime.now(timezone.utc)
    records = []
    for symbol in symbols:
        quote = latest.get(symbol)
        if not quote:
            print(f"  ⚠️ {symbol}: no streaming quote received within {timeout_sec}s")
            continue
        record = build_orderbook_record(symbol, quote, now)
        if record:
            records.append(record)
        else:
            print(f"  ⚠️ {symbol}: streaming quote could not be mapped to orderbook_snapshot")
    if records:
        db.upsert_orderbook(records)
    print(f"📚 streaming orderbook_snapshot upserted: {len(records)}")
    return len(records)


def snapshot_orderbook(symbols: list[str] | None = None, db: SupabaseClient | None = None, debug: bool = False, timeout_sec: int | None = None) -> int:
    """Primary orderbook snapshot entrypoint: use SSI Streaming quote, not REST."""
    return snapshot_orderbook_from_stream(symbols=symbols, timeout_sec=timeout_sec, db=db, debug=debug)
