from __future__ import annotations

import hashlib
import json
import time as monotonic_time
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from src.config import config
from src.database.client import SupabaseClient
from src.ssi.streaming import SSIStreamingClient, normalize_stream_payload
from src.validation.models import ValidationIssue
from src.validation.streaming_validator import validate_stream_record

VN_TZ = timezone(timedelta(hours=7))


def _get_any(data: dict[str, Any], *keys: str) -> Any:
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
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _parse_trading_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_stream_time(payload: dict[str, Any], snapshot_time: datetime | None = None) -> datetime | None:
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    raw_time = _get_any(payload, "Time", "TradingTime", "time", "tradingTime")
    if isinstance(raw_time, datetime):
        return raw_time.astimezone(timezone.utc) if raw_time.tzinfo else raw_time.replace(tzinfo=VN_TZ).astimezone(timezone.utc)
    text = str(raw_time).strip() if raw_time not in (None, "") else ""
    if text:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%H:%M:%S.%f", "%H:%M:%S", "%H%M%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                if parsed.tzinfo is None:
                    if parsed.date() == date(1900, 1, 1) and trading_date:
                        parsed = datetime.combine(trading_date, parsed.time())
                    parsed = parsed.replace(tzinfo=VN_TZ)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                continue
    return None


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None

def _issues_to_json(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    return [issue.__dict__ for issue in issues]

def _payload_hash(channel: str, payload: dict[str, Any], received_at: datetime) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(f"{channel}|{received_at.isoformat()}|{body}".encode("utf-8")).hexdigest()


def _common_price_fields(payload: dict[str, Any], snapshot_time: datetime) -> dict[str, Any]:
    dt = _parse_stream_time(payload, snapshot_time)
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    return {
        "time": _iso(dt),
        "trading_date": trading_date.isoformat() if trading_date else None,
        "exchange": _get_any(payload, "Exchange", "exchange"),
        "market_id": _get_any(payload, "MarketId", "MarketID", "marketId", "marketid"),
        "trading_session": _get_any(payload, "TradingSession", "tradingSession"),
        "trading_status": _get_any(payload, "TradingStatus", "tradingStatus"),
        "ceiling": _to_float(_get_any(payload, "Ceiling", "CeilingPrice")),
        "floor": _to_float(_get_any(payload, "Floor", "FloorPrice")),
        "ref_price": _to_float(_get_any(payload, "RefPrice", "ReferencePrice")),
        "open": _to_float(_get_any(payload, "Open", "OpenPrice")),
        "close": _to_float(_get_any(payload, "Close", "ClosePrice")),
        "high": _to_float(_get_any(payload, "High", "Highest", "HighPrice")),
        "low": _to_float(_get_any(payload, "Low", "Lowest", "LowPrice")),
        "avg_price": _to_float(_get_any(payload, "AvgPrice", "AveragePrice")),
        "last_price": _to_float(_get_any(payload, "LastPrice", "Last", "LastMatchedPrice", "MatchedPrice")),
        "last_vol": _to_int(_get_any(payload, "LastVol", "LastVolume", "MatchedVol", "MatchedVolume")),
        "total_vol": _to_int(_get_any(payload, "TotalVol", "TotalVolume", "TotalQtty")),
        "total_val": _to_int(_get_any(payload, "TotalVal", "TotalValue")),
        "change": _to_float(_get_any(payload, "Change", "ChangePrice")),
        "ratio_change": _to_float(_get_any(payload, "RatioChange", "PercentChange", "ChangePercent")),
        "est_matched_price": _to_float(_get_any(payload, "EstMatchedPrice", "EstimatedMatchedPrice")),
        "raw": payload,
    }


def build_raw_stream_record(channel: str, payload: dict[str, Any], received_at: datetime | None = None, validation_status: str = "PENDING", validation_issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    received_at = received_at or datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    dt = _parse_stream_time(payload)
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    return {"channel": channel, "requested_channel": channel, "rtype": _get_any(payload, "RType", "DataType"), "symbol": _get_any(payload, "Symbol", "symbol"), "index_code": _get_any(payload, "IndexId", "IndexID", "indexid", "IndexCode"), "time": _iso(dt), "source_time": _iso(dt), "received_at": _iso(received_at), "trading_date": trading_date.isoformat() if trading_date else None, "payload": payload, "payload_hash": _payload_hash(channel, payload, received_at), "validation_status": validation_status, "validation_issues": validation_issues or []}


def build_quote_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    snapshot_time = snapshot_time or datetime.now(timezone.utc)
    symbol = _get_any(payload, "Symbol", "symbol")
    if not symbol:
        return None
    record = {"symbol": str(symbol).upper(), **_common_price_fields(payload, snapshot_time)}
    bid_depths: list[int] = []
    ask_depths: list[int] = []
    for i in range(1, 11):
        record[f"bid_price_{i}"] = _to_float(_get_any(payload, f"BidPrice{i}", f"bidPrice{i}"))
        bid_vol = _to_int(_get_any(payload, f"BidVol{i}", f"BidVolume{i}", f"bidVol{i}", f"bidVolume{i}"))
        record[f"bid_vol_{i}"] = bid_vol
        record[f"ask_price_{i}"] = _to_float(_get_any(payload, f"AskPrice{i}", f"askPrice{i}"))
        ask_vol = _to_int(_get_any(payload, f"AskVol{i}", f"AskVolume{i}", f"askVol{i}", f"askVolume{i}"))
        record[f"ask_vol_{i}"] = ask_vol
        if bid_vol is not None:
            bid_depths.append(bid_vol)
        if ask_vol is not None:
            ask_depths.append(ask_vol)
    total_bid = sum(bid_depths) if bid_depths else None
    total_ask = sum(ask_depths) if ask_depths else None
    total = (total_bid or 0) + (total_ask or 0) if total_bid is not None or total_ask is not None else None
    record["total_bid_depth_10"] = total_bid
    record["total_ask_depth_10"] = total_ask
    record["orderbook_imbalance"] = (total_bid / total) if total and total_bid is not None else None
    record["pressure_score"] = (((total_bid or 0) - (total_ask or 0)) / total) if total else None
    return record


def build_trade_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    symbol = _get_any(payload, "Symbol", "symbol")
    return {"symbol": str(symbol).upper(), **_common_price_fields(payload, snapshot_time or datetime.now(timezone.utc))} if symbol else None


def build_foreign_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    symbol = _get_any(payload, "Symbol", "symbol")
    if not symbol:
        return None
    dt = _parse_stream_time(payload, snapshot_time or datetime.now(timezone.utc))
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    buy_vol = _to_int(_get_any(payload, "ForeignBuyVol", "BuyVol", "FBuyVol"))
    sell_vol = _to_int(_get_any(payload, "ForeignSellVol", "SellVol", "FSellVol"))
    buy_val = _to_int(_get_any(payload, "ForeignBuyVal", "BuyVal", "FBuyVal"))
    sell_val = _to_int(_get_any(payload, "ForeignSellVal", "SellVal", "FSellVal"))
    return {"symbol": str(symbol).upper(), "time": _iso(dt), "trading_date": trading_date.isoformat() if trading_date else None, "exchange": _get_any(payload, "Exchange"), "market_id": _get_any(payload, "MarketId", "MarketID"), "total_room": _to_int(_get_any(payload, "TotalRoom", "Room")), "current_room": _to_int(_get_any(payload, "CurrentRoom", "RemainRoom")), "foreign_buy_vol": buy_vol, "foreign_sell_vol": sell_vol, "foreign_buy_val": buy_val, "foreign_sell_val": sell_val, "net_foreign_vol": (buy_vol - sell_vol) if buy_vol is not None and sell_vol is not None else None, "net_foreign_val": (buy_val - sell_val) if buy_val is not None and sell_val is not None else None, "raw": payload}


def build_index_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    index_code = _get_any(payload, "IndexId", "IndexID", "indexid", "IndexCode")
    if not index_code:
        return None
    dt = _parse_stream_time(payload, snapshot_time or datetime.now(timezone.utc))
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    fields = {"index_value": ("IndexValue",), "index_val_est": ("IndexValEst",), "prior_index_value": ("PriorIndexValue",), "change": ("Change",), "ratio_change": ("RatioChange",), "total_trade": ("TotalTrade",), "total_qtty": ("TotalQtty",), "total_value": ("TotalValue",), "total_qtty_pt": ("TotalQttyPT",), "total_value_pt": ("TotalValuePT",), "total_qtty_od": ("TotalQttyOD",), "total_value_od": ("TotalValueOD",), "all_qty": ("AllQty",), "all_value": ("AllValue",), "advances": ("Advances",), "no_changes": ("NoChanges",), "declines": ("Declines",), "ceilings": ("Ceilings",), "floors": ("Floors",)}
    rec: dict[str, Any] = {"index_code": str(index_code).upper(), "time": _iso(dt), "trading_date": trading_date.isoformat() if trading_date else None, "exchange": _get_any(payload, "Exchange"), "market": _get_any(payload, "Market"), "index_type": _get_any(payload, "IndexType"), "index_name": _get_any(payload, "IndexName"), "trading_session": _get_any(payload, "TradingSession"), "raw": payload}
    for out, keys in fields.items():
        rec[out] = _to_int(_get_any(payload, *keys)) if out not in {"index_value", "index_val_est", "prior_index_value", "change", "ratio_change"} else _to_float(_get_any(payload, *keys))
    return rec



def build_status_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    symbol = _get_any(payload, "Symbol", "symbol")
    if not symbol:
        return None
    dt = _parse_stream_time(payload)
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    return {"symbol": str(symbol).upper(), "time": _iso(dt), "trading_date": trading_date.isoformat() if trading_date else None, "exchange": _get_any(payload, "Exchange"), "market_id": _get_any(payload, "MarketId", "MarketID"), "trading_session": _get_any(payload, "TradingSession"), "trading_status": _get_any(payload, "TradingStatus"), "raw": payload}


def build_bar_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    symbol = _get_any(payload, "Symbol", "symbol")
    if not symbol:
        return None
    dt = _parse_stream_time(payload)
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    return {"symbol": str(symbol).upper(), "time": _iso(dt), "trading_date": trading_date.isoformat() if trading_date else None, "exchange": _get_any(payload, "Exchange"), "market_id": _get_any(payload, "MarketId", "MarketID"), "open": _to_float(_get_any(payload, "Open", "OpenPrice")), "high": _to_float(_get_any(payload, "High", "HighPrice")), "low": _to_float(_get_any(payload, "Low", "LowPrice")), "close": _to_float(_get_any(payload, "Close", "ClosePrice")), "volume": _to_int(_get_any(payload, "Volume", "Vol")), "value": _to_int(_get_any(payload, "Value")), "raw": payload}

def _channel_type(channel: str, rtype: str | None) -> str:
    base = channel.split(":", 1)[0].upper()
    r = (rtype or base).upper()
    if r == "QUOTE": return "X-QUOTE"
    if r == "TRADE": return "X-TRADE"
    return r if r in {"F", "X-QUOTE", "X-TRADE", "R", "MI", "B"} else base

def _status_from_counts(raw_received: int, invalid: int, failures: list[str], subscribed: list[str]) -> str:
    if failures:
        return "FAILED"
    if raw_received == 0:
        return "EMPTY"
    if invalid or raw_received < len(subscribed):
        return "PARTIAL"
    return "OK"

def build_streaming_channels(symbols: list[str], indexes: list[str], channel_names: list[str]) -> list[str]:
    mapping = {"securities-status": "F", "quote": "X-QUOTE", "trade": "X-TRADE", "foreign-room": "R", "index": "MI", "realtime-bar": "B"}
    out: list[str] = []
    for name in channel_names:
        prefix = mapping[name]
        values = indexes if name == "index" else symbols
        out.extend(f"{prefix}:{str(v).upper()}" for v in values)
    return out

def run_streaming_ingest(symbols: list[str], indexes: list[str], channels: list[str], timeout_sec: int = 60, max_messages_per_channel: int = 1, write: bool = False, debug: bool = False, client: SSIStreamingClient | None = None, db: SupabaseClient | None = None) -> dict[str, Any]:
    if not symbols and any(c != "index" for c in channels):
        raise ValueError("symbols are required for non-index streaming channels")
    if not indexes and "index" in channels:
        raise ValueError("indexes are required for index streaming channel")
    if timeout_sec <= 0 or timeout_sec > 3600:
        raise ValueError("timeout must be between 1 and 3600 seconds")
    if max_messages_per_channel <= 0 or max_messages_per_channel > 1000:
        raise ValueError("max_messages_per_channel must be between 1 and 1000")
    requested = build_streaming_channels(symbols, indexes, channels)
    started = datetime.now(timezone.utc)
    client = client or SSIStreamingClient()
    raw_records=[]; clean = {"quote": [], "trade": [], "foreign": [], "index": [], "status": [], "bar": []}
    invalid_counts: dict[str, int] = {}; failures: list[str] = []
    try:
        client.connect(); client.subscribe_many(requested)
        latest: dict[str, dict[str, Any]] = {}
        deadline = monotonic_time.monotonic() + timeout_sec
        while monotonic_time.monotonic() < deadline and any(sum(1 for k in latest if k == ch) < max_messages_per_channel for ch in requested):
            for raw in client.listen(timeout_sec=1, max_messages=20):
                parsed = client.parse_message(raw); norm = normalize_stream_payload(parsed)
                content = norm.get("raw") if isinstance(norm.get("raw"), dict) else parsed
                rtype = _channel_type(str(norm.get("RType") or norm.get("DataType") or ""), None)
                symbol = norm.get("Symbol"); idx = norm.get("IndexId")
                candidates = []
                if symbol: candidates.append(f"{rtype}:{symbol}".upper())
                if idx: candidates.append(f"{rtype}:{idx}".upper())
                matched = next((ch for ch in requested if ch.upper() in candidates), None)
                if not matched: continue
                latest[matched] = content
                received_at = datetime.now(timezone.utc)
                stype = _channel_type(matched, str(norm.get("RType") or norm.get("DataType") or ""))
                builder = {"F": build_status_snapshot_record, "X-QUOTE": build_quote_snapshot_record, "X-TRADE": build_trade_snapshot_record, "R": build_foreign_snapshot_record, "MI": build_index_snapshot_record, "B": build_bar_snapshot_record}.get(stype)
                rec = builder(content, received_at) if builder else None
                validation = validate_stream_record(rec or {}, stype)
                issues = _issues_to_json(validation.errors + validation.warnings)
                raw_records.append(build_raw_stream_record(matched, content, received_at, "ERROR" if validation.errors else ("WARNING" if validation.warnings else "OK"), issues))
                if validation.errors or rec is None:
                    invalid_counts[stype] = invalid_counts.get(stype, 0) + 1
                    continue
                {"F": clean["status"], "X-QUOTE": clean["quote"], "X-TRADE": clean["trade"], "R": clean["foreign"], "MI": clean["index"], "B": clean["bar"]}[stype].append(rec)
        if write and raw_records:
            db = db or SupabaseClient()
            db.upsert_stream_raw(raw_records)
            db.upsert_stream_quote(clean["quote"]); db.upsert_stream_trade(clean["trade"]); db.upsert_stream_foreign_snapshot(clean["foreign"]); db.upsert_stream_index_snapshot(clean["index"]); db.upsert_stream_status_snapshot(clean["status"]); db.upsert_stream_bar_snapshot(clean["bar"])
    except Exception as exc:
        failures.append(str(exc))
    finally:
        client.close()
    ended = datetime.now(timezone.utc)
    raw_received = len(raw_records)
    return {"status": _status_from_counts(raw_received, sum(invalid_counts.values()), failures, requested), "write": write, "requested_channels": requested, "subscribed_channels": getattr(client, "subscribed_channels", []), "raw_received": raw_received, "raw_written": len(raw_records) if write and not failures else 0, "clean_valid": {k: len(v) for k, v in clean.items()}, "clean_written": {k: (len(v) if write and not failures else 0) for k, v in clean.items()}, "invalid": invalid_counts, "warning_count": sum(1 for r in raw_records if r.get("validation_status") == "WARNING"), "empty_channels": [ch for ch in requested if ch not in latest], "failure_stage": "runtime" if failures else None, "failure_reason": failures[0] if failures else None, "start_time": _iso(started), "end_time": _iso(ended), "elapsed_sec": round((ended-started).total_seconds(), 3)}

def snapshot_market_stream(symbols: list[str], indexes: list[str] = ["VNINDEX", "VN30"], timeout_sec: int = 60, write: bool = True, debug: bool = False) -> dict[str, int]:
    channels = [c for s in symbols for c in (f"X-QUOTE:{s.upper()}", f"X-TRADE:{s.upper()}", f"R:{s.upper()}")] + [f"MI:{i.upper()}" for i in indexes]
    client = SSIStreamingClient()
    raw_records=[]; quote_records=[]; trade_records=[]; foreign_records=[]; index_records=[]
    try:
        client.connect()
        latest = client.collect_latest_by_channels(channels, timeout_sec=timeout_sec, debug=debug)
        snap = datetime.now(timezone.utc)
        for channel, payload in latest.items():
            norm = normalize_stream_payload(payload)
            content = norm.get("raw") if isinstance(norm.get("raw"), dict) else payload
            rtype = str(norm.get("RType") or channel.split(":", 1)[0]).upper()
            raw_records.append(build_raw_stream_record(channel, content, snap))
            if rtype in ("X-QUOTE", "QUOTE"):
                rec = build_quote_snapshot_record(content, snap)
                if rec: quote_records.append(rec)
            elif rtype in ("X-TRADE", "TRADE"):
                rec = build_trade_snapshot_record(content, snap)
                if rec: trade_records.append(rec)
            elif rtype == "R":
                rec = build_foreign_snapshot_record(content, snap)
                if rec: foreign_records.append(rec)
            elif rtype == "MI":
                rec = build_index_snapshot_record(content, snap)
                if rec: index_records.append(rec)
        if write:
            db = SupabaseClient()
            db.upsert_stream_raw(raw_records); db.upsert_stream_quote(quote_records); db.upsert_stream_trade(trade_records); db.upsert_stream_foreign_snapshot(foreign_records); db.upsert_stream_index_snapshot(index_records)
        return {"raw": len(raw_records), "quote": len(quote_records), "trade": len(trade_records), "foreign": len(foreign_records), "index": len(index_records)}
    finally:
        client.close()
