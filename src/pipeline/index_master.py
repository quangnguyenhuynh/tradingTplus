"""SSI index definitions and constituent master-data synchronization."""
from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi


def _value(item: dict, *keys: str) -> Any:
    lower = {str(key).lower(): value for key, value in item.items()}
    for key in keys:
        if key.lower() in lower:
            return lower[key.lower()]
    return None


def map_index_master_record(item: dict) -> dict | None:
    code = _value(item, "IndexCode", "IndexId")
    if code in (None, ""):
        return None
    return {"index_code": str(code).strip(), "index_name": _value(item, "IndexName"), "exchange": _value(item, "Exchange"), "raw": item}


def map_index_component_record(item: dict, requested_code: str) -> dict | None:
    symbol = _value(item, "StockSymbol", "Symbol")
    code = _value(item, "IndexCode", "IndexId") or requested_code
    if symbol in (None, "") or code in (None, ""):
        return None
    return {"index_code": str(code).strip(), "symbol": str(symbol).strip().upper(), "exchange": _value(item, "Exchange"), "raw": item}


def sync_index_master(ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> list[str]:
    ssi, db = ssi or SSIApi(), db or SupabaseClient()
    items = [item for exchange in ("HOSE", "HNX", "UPCOM") for item in ssi.get_index_list(exchange=exchange)]
    records = [record for item in items if (record := map_index_master_record(item))]
    if records:
        writer = getattr(db, "upsert_index_master", None) or db.upsert_indexes
        writer(records)
    return [record["index_code"] for record in records]


def sync_index_components(index_codes: list[str] | None = None, ssi: SSIApi | None = None, db: SupabaseClient | None = None) -> int:
    ssi, db = ssi or SSIApi(), db or SupabaseClient()
    codes = index_codes if index_codes is not None else sync_index_master(ssi, db)
    records = [record for code in codes for item in ssi.get_index_components(code) if (record := map_index_component_record(item, code))]
    if records:
        db.upsert_index_components(records)
    return len(records)


# Compatibility names retained for existing imports.
sync_indexes = sync_index_master
map_index_record = map_index_master_record
