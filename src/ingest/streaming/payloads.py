"""Offline historical snapshot decoding; no streaming connection implementation."""
from __future__ import annotations
import json
from typing import Any
def _json_loads_maybe(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def parse_message(raw: Any) -> dict[str, Any]:
    original = raw
    if isinstance(raw, (list, tuple)):
        if len(raw) == 1:
            raw = raw[0]
        elif len(raw) >= 2:
            raw = {"data_type": raw[0], "content": raw[1], "args": list(raw)}
    raw = _json_loads_maybe(raw)
    data_type = None
    content: Any = raw
    if isinstance(raw, dict):
        data_type = raw.get("DataType") or raw.get("datatype") or raw.get("dataType") or raw.get("type") or raw.get("RType")
        for key in ("Content", "content", "Data", "data", "payload", "Payload"):
            if key in raw:
                content = raw[key]
                break
    content = _json_loads_maybe(content)
    if isinstance(content, dict) and data_type is None:
        data_type = content.get("DataType") or content.get("datatype") or content.get("dataType") or content.get("type") or content.get("RType")
    return {"data_type": data_type, "content": content, "raw": original}


def _get_any(data: dict, *keys: str) -> Any:
    lowered = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def normalize_quote(parsed: dict[str, Any]) -> dict[str, Any]:
    content = parsed.get("content")
    if not isinstance(content, dict):
        return {"raw": parsed}
    quote = {
        "data_type": parsed.get("data_type"),
        "symbol": _get_any(content, "Symbol", "symbol"),
        "trading_date": _get_any(content, "TradingDate", "tradingDate"),
        "time": _get_any(content, "Time", "TradingTime", "time", "tradingTime"),
        "exchange": _get_any(content, "Exchange", "exchange"),
        "trading_session": _get_any(content, "TradingSession", "tradingSession"),
        "trading_status": _get_any(content, "TradingStatus", "tradingStatus"),
        "last_price": _get_any(content, "LastPrice", "Last", "LastMatchedPrice", "lastPrice"),
        "total_vol": _get_any(content, "TotalVol", "totalVol"),
        "total_val": _get_any(content, "TotalVal", "totalVal"),
        "raw": content,
    }
    if quote["symbol"]:
        quote["symbol"] = str(quote["symbol"]).upper()
    for level in range(1, 11):
        quote[f"bid_price_{level}"] = _get_any(content, f"BidPrice{level}", f"bidPrice{level}")
        quote[f"bid_vol_{level}"] = _get_any(content, f"BidVol{level}", f"BidVolume{level}", f"bidVol{level}", f"bidVolume{level}")
        quote[f"ask_price_{level}"] = _get_any(content, f"AskPrice{level}", f"askPrice{level}")
        quote[f"ask_vol_{level}"] = _get_any(content, f"AskVol{level}", f"AskVolume{level}", f"askVol{level}", f"askVolume{level}")
    return quote


def normalize_stream_payload(parsed_message: Any) -> dict[str, Any]:
    """Normalize any SSI market streaming payload without assuming X-QUOTE only."""
    parsed = parsed_message if isinstance(parsed_message, dict) and "content" in parsed_message else parse_message(parsed_message)
    content = parsed.get("content")
    if not isinstance(content, dict):
        return {"RType": parsed.get("data_type"), "DataType": parsed.get("data_type"), "raw": parsed}
    rtype = _get_any(content, "RType", "DataType", "dataType", "type") or parsed.get("data_type")
    symbol = _get_any(content, "Symbol", "symbol")
    index_code = _get_any(content, "IndexId", "IndexID", "indexid", "IndexCode", "indexCode")
    normalized = {
        "RType": rtype,
        "DataType": _get_any(content, "DataType", "dataType") or parsed.get("data_type"),
        "Symbol": str(symbol).upper() if symbol else None,
        "IndexId": str(index_code).upper() if index_code else None,
        "TradingDate": _get_any(content, "TradingDate", "tradingDate"),
        "Time": _get_any(content, "Time", "TradingTime", "time", "tradingTime"),
        "Exchange": _get_any(content, "Exchange", "exchange"),
        "MarketId": _get_any(content, "MarketId", "MarketID", "marketId", "marketid"),
        "raw": content,
    }
    if not normalized["RType"]:
        # Infer from fields as a fallback for SignalR payloads that omit RType.
        if normalized["IndexId"]:
            normalized["RType"] = "MI"
        elif any(_get_any(content, f"BidPrice{i}", f"AskPrice{i}") is not None for i in range(1, 11)):
            normalized["RType"] = "X-QUOTE"
    return normalized
