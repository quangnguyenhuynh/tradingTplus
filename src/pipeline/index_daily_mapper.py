"""Pure SSI DailyIndex raw and clean mapping."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from src.pipeline.date_utils import parse_ddmmyyyy


INDEX_DAILY_CLEAN_SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "index_code": ("IndexCode", "IndexId", "indexcode", "indexid"),
    "trading_date": ("TradingDate",),
    "index_value": ("IndexValue",),
    "change": ("Change",),
    "ratio_change": ("RatioChange",),
    "total_trade": ("TotalTrade",),
    "total_match_vol": ("TotalMatchVol",),
    "total_match_val": ("TotalMatchVal",),
    "type_index": ("TypeIndex",),
    "index_name": ("IndexName",),
    "advances": ("Advances",),
    "no_changes": ("NoChanges", "Nochanges"),
    "declines": ("Declines",),
    "ceilings": ("Ceilings", "Ceiling"),
    "floors": ("Floors", "Floor"),
    "total_deal_vol": ("TotalDealVol",),
    "total_deal_val": ("TotalDealVal",),
    "total_vol": ("TotalVol",),
    "total_val": ("TotalVal",),
    "trading_session": ("TradingSession",),
    "market": ("Market",),
    "exchange": ("Exchange",),
}


def get_index_payload_value(payload: dict, *keys: str) -> Any:
    lower = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        if key.lower() in lower:
            return lower[key.lower()]
    return None


def payload_index_code(payload: dict) -> str | None:
    value = get_index_payload_value(payload, *INDEX_DAILY_CLEAN_SOURCE_ALIASES["index_code"])
    return str(value).strip() if value not in (None, "") else None


def payload_index_date(payload: dict) -> str | None:
    value = get_index_payload_value(payload, *INDEX_DAILY_CLEAN_SOURCE_ALIASES["trading_date"])
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        # Retain malformed source evidence in-memory so validation rejects it;
        # invalid values are never sent to the numeric clean table.
        return value


def build_index_raw_daily_record(requested_code: str, date: str, payload: dict) -> dict:
    code = payload_index_code(payload) or requested_code
    trading_date = payload_index_date(payload) or parse_ddmmyyyy(date).iso
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return {"index_code": code, "trading_date": trading_date, "data_hash": hashlib.sha256(canonical.encode()).hexdigest(), "payload": payload, "source": "SSI_DailyIndex"}


def build_index_daily_record(requested_code: str, date: str, payload: dict) -> dict | None:
    source_code, source_date = payload_index_code(payload), payload_index_date(payload)
    if source_code is None or source_date is None:
        return None
    if source_code.casefold() != requested_code.casefold() or source_date != parse_ddmmyyyy(date).iso:
        return None
    numeric = (
        "index_value", "change", "ratio_change", "total_trade", "total_match_vol",
        "total_match_val", "total_deal_vol", "total_deal_val", "total_vol",
        "total_val", "advances", "no_changes", "declines", "ceilings", "floors",
    )
    record = {"index_code": requested_code, "trading_date": source_date}
    record.update({
        field: _number(get_index_payload_value(payload, *INDEX_DAILY_CLEAN_SOURCE_ALIASES[field]))
        for field in numeric
    })
    for field in ("type_index", "index_name", "trading_session", "market", "exchange"):
        record[field] = get_index_payload_value(payload, *INDEX_DAILY_CLEAN_SOURCE_ALIASES[field])
    return record


def summarize_index_payload_mapping(payload: dict, record: dict | None) -> dict[str, Any]:
    """Expose source keys not represented by the normalized clean contract."""
    clean_aliases = {
        alias.casefold()
        for aliases in INDEX_DAILY_CLEAN_SOURCE_ALIASES.values()
        for alias in aliases
    }
    omitted = [str(key) for key in payload if str(key).casefold() not in clean_aliases]
    return {
        "raw_field_count": len(payload),
        "normalized_field_count": len(record) if record is not None else 0,
        "omitted_from_clean": omitted,
    }
