from __future__ import annotations
import json, re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
from src.config import config
from src.ssi.streaming import parse_message
from .registry import STREAM_TYPES

SENSITIVE_RE = re.compile(r"(token|accesstoken|connectiontoken|consumerid|consumersecret|authorization|cookie|set-cookie)", re.I)
TOKEN_QS_RE = re.compile(r"(connectionToken|accessToken|token)=([^&\s]+)", re.I)
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I)

def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SENSITIVE_RE.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, tuple): return tuple(redact(v) for v in value)
    if isinstance(value, str):
        value = TOKEN_QS_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
        return BEARER_RE.sub("Bearer [REDACTED]", value)
    return value

def find_token_paths(value: Any, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            p = f"{prefix}.{k}"
            if SENSITIVE_RE.search(str(k)): paths.append(p)
            paths.extend(find_token_paths(v, p))
    elif isinstance(value, list):
        for i, v in enumerate(value): paths.extend(find_token_paths(v, f"{prefix}[{i}]"))
    return paths

def _get_any(d: dict[str, Any], *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        if k in d: return d[k]
        if k.lower() in lower: return lower[k.lower()]
    return None

def decode_signalr_frame(raw_text: Any) -> dict[str, Any]:
    frame = {"raw": raw_text, "frame_type": type(raw_text).__name__, "frame_length": len(raw_text) if isinstance(raw_text, (str, bytes)) else None, "messages": []}
    try: obj = json.loads(raw_text) if isinstance(raw_text, str) else raw_text
    except Exception:
        frame["malformed"] = True; frame["sample"] = redact(str(raw_text)[:500]); return frame
    frame["top_level_keys"] = sorted(obj.keys()) if isinstance(obj, dict) else []
    for item in (obj.get("M") if isinstance(obj, dict) else []) or []:
        args = item.get("A") or [] if isinstance(item, dict) else []
        frame["messages"].append({"method": item.get("M"), "args_count": len(args), "args": args})
    return frame

def inspect_arg(arg: Any, kind: str | None, requested_channel: str, seq: int, raw_frame: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    parsed = parse_message(arg)
    content = parsed.get("content")
    content_keys = sorted(content.keys()) if isinstance(content, dict) else []
    expected = set(STREAM_TYPES[kind].expected_fields) if kind in STREAM_TYPES else set()
    actual = set(content_keys)
    aliases = {"Time":"TradingTime", "TradingTime":"Time", "Rtype":"RType", "RType":"Rtype", "MarketId":"MarketID", "MarketID":"MarketId", "IndexId":"IndexID", "IndexID":"IndexId", "Avg":"AvgPrice", "AvgPrice":"Avg", "FBuyVol":"BuyVol", "BuyVol":"FBuyVol", "FSellVol":"SellVol", "SellVol":"FSellVol", "FBuyVal":"BuyVal", "BuyVal":"FBuyVal", "FSellVal":"SellVal", "SellVal":"FSellVal"}
    missing = sorted(f for f in expected if f not in actual and aliases.get(f) not in actual)
    extra = sorted(actual - expected)
    return redact({
        "sequence": seq, "received_utc": now.isoformat(), "received_vietnam": now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(), "requested_channel": requested_channel,
        "raw_frame_type": (raw_frame or {}).get("frame_type"), "raw_frame_length": (raw_frame or {}).get("frame_length"), "signalr_top_level_keys": (raw_frame or {}).get("top_level_keys", []),
        "callback_method": (raw_frame or {}).get("method", config.SSI_SIGNALR_RECEIVE_METHOD), "args_count": (raw_frame or {}).get("args_count"),
        "data_type": parsed.get("data_type"), "rtype": _get_any(content, "RType", "Rtype") if isinstance(content, dict) else None,
        "symbol": _get_any(content, "Symbol") if isinstance(content, dict) else None, "index_id": _get_any(content, "IndexId", "IndexID") if isinstance(content, dict) else None,
        "trading_date": _get_any(content, "TradingDate") if isinstance(content, dict) else None, "time": _get_any(content, "Time", "TradingTime") if isinstance(content, dict) else None,
        "content_keys": content_keys, "field_count": len(content_keys), "extra_fields_not_in_registry": extra, "missing_registry_fields": missing,
        "decoded_content_sample": content if isinstance(content, dict) else parsed,
    })

def dump_json(value: Any) -> str:
    return json.dumps(redact(value), indent=2, ensure_ascii=False, default=str)
