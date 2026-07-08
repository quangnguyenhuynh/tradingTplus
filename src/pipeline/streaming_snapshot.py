from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from src.config import config
from src.database.client import SupabaseClient
from src.ssi.streaming import SSIStreamingClient, normalize_stream_payload

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


def _parse_stream_time(payload: dict[str, Any], snapshot_time: datetime | None = None) -> datetime:
    fallback = snapshot_time or datetime.now(timezone.utc)
    if fallback.tzinfo is None:
        fallback = fallback.replace(tzinfo=timezone.utc)
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
    if trading_date:
        return datetime.combine(trading_date, time.min, tzinfo=VN_TZ).astimezone(timezone.utc)
    return fallback.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


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


def build_raw_stream_record(channel: str, payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any]:
    snapshot_time = snapshot_time or datetime.now(timezone.utc)
    dt = _parse_stream_time(payload, snapshot_time)
    trading_date = _parse_trading_date(_get_any(payload, "TradingDate", "tradingDate"))
    return {"channel": channel, "rtype": _get_any(payload, "RType", "DataType"), "symbol": _get_any(payload, "Symbol", "symbol"), "index_code": _get_any(payload, "IndexId", "IndexID", "indexid"), "time": _iso(dt), "trading_date": trading_date.isoformat() if trading_date else None, "payload": payload}


def build_quote_snapshot_record(payload: dict[str, Any], snapshot_time: datetime | None = None) -> dict[str, Any] | None:
    snapshot_time = snapshot_time or datetime.now(timezone.utc)
    symbol = _get_any(payload, "Symbol", "symbol")
    if not symbol:
        return None
    record = {"symbol": str(symbol).upper(), **_common_price_fields(payload, snapshot_time)}
    total_bid = 0
    total_ask = 0
    for i in range(1, 11):
        record[f"bid_price_{i}"] = _to_float(_get_any(payload, f"BidPrice{i}", f"bidPrice{i}"))
        bid_vol = _to_int(_get_any(payload, f"BidVol{i}", f"BidVolume{i}", f"bidVol{i}", f"bidVolume{i}"))
        record[f"bid_vol_{i}"] = bid_vol
        record[f"ask_price_{i}"] = _to_float(_get_any(payload, f"AskPrice{i}", f"askPrice{i}"))
        ask_vol = _to_int(_get_any(payload, f"AskVol{i}", f"AskVolume{i}", f"askVol{i}", f"askVolume{i}"))
        record[f"ask_vol_{i}"] = ask_vol
        total_bid += bid_vol or 0
        total_ask += ask_vol or 0
    total = total_bid + total_ask
    record["total_bid_depth_10"] = total_bid
    record["total_ask_depth_10"] = total_ask
    record["orderbook_imbalance"] = total_bid / total if total else 0.5
    record["pressure_score"] = (total_bid - total_ask) / total if total else 0
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
    return {"symbol": str(symbol).upper(), "time": _iso(dt), "trading_date": trading_date.isoformat() if trading_date else None, "exchange": _get_any(payload, "Exchange"), "market_id": _get_any(payload, "MarketId", "MarketID"), "total_room": _to_int(_get_any(payload, "TotalRoom", "Room")), "current_room": _to_int(_get_any(payload, "CurrentRoom", "RemainRoom")), "foreign_buy_vol": buy_vol, "foreign_sell_vol": sell_vol, "foreign_buy_val": buy_val, "foreign_sell_val": sell_val, "net_foreign_vol": (buy_vol or 0) - (sell_vol or 0), "net_foreign_val": (buy_val or 0) - (sell_val or 0), "raw": payload}


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
