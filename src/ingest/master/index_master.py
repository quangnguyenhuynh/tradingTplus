"""SSI index definitions and constituent master-data synchronization."""
from __future__ import annotations
from src.providers.ssi.capabilities import CapabilityUnavailableError

from typing import Any

from src.database.client import SupabaseClient


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


def sync_index_master(ssi: Any | None = None, db: SupabaseClient | None = None) -> list[str]:
    raise CapabilityUnavailableError("master")


def sync_index_components(index_codes: list[str] | None = None, ssi: Any | None = None, db: SupabaseClient | None = None) -> int:
    raise CapabilityUnavailableError("master")


# Compatibility names retained for existing imports.
sync_indexes = sync_index_master
map_index_record = map_index_master_record
