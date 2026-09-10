"""Production single-day SSI DailyIndex ingestion."""
from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import (
    latest_weekday_on_or_before,
    parse_index_date,
    validate_safe_write_date,
)
from src.pipeline.index_daily_service import fetch_index_daily_with_clients
from src.pipeline.index_scope import index_scope_summary, resolve_index_scope
from src.ssi.api import SSIApi
from src.data_sources.registry import resolve_source
from src.data_sources.ssi_v2 import SSIV2Adapter


def _resolve_index_daily_date(date: str | None) -> str:
    if date is None or not str(date).strip():
        resolved = latest_weekday_on_or_before().strftime("%d/%m/%Y")
        print(f"📆 Index daily date defaulted to latest weekday on/before today (VN): {resolved}")
        return resolved
    validated = parse_index_date(date.strip())
    validate_safe_write_date(validated)
    return validated.ddmmyyyy


def run_index_daily_ingest(date: str | None = None, indexes: list[str] | tuple[str, ...] | None = None, data_source: str | None = None) -> dict[str, Any]:
    resolved_date = _resolve_index_daily_date(date)
    capability = resolve_source("index_daily", data_source)
    print(f"ℹ️ Dataset: index_daily; data source: {capability.source}")
    db = SupabaseClient()
    resolved, requested = resolve_index_scope(db, indexes)
    ssi = SSIV2Adapter(SSIApi())
    rows = [fetch_index_daily_with_clients(ssi, db, code, resolved_date) for code in resolved]
    clean_count = sum(item["clean_rows"] for item in rows)
    raw_count = sum(item["raw_rows"] for item in rows)
    failed = sum(item["status"] == "FAILED" for item in rows)
    partial = sum(item["status"] == "PARTIAL" for item in rows)
    status = "FAILED" if failed == len(rows) else "PARTIAL" if failed or partial else "OK"
    return {"flow": "index-daily", "date": resolved_date, "data_source": capability.source, **index_scope_summary(resolved, requested), "index_raw_daily_count": raw_count, "index_daily_count": clean_count, "error_count": sum(len(item["errors"]) for item in rows), "per_index": rows, "status": status}


# Compatibility helper replacing the removed mixed index_data implementation.
def fetch_daily_indexes(date: str, index_codes=None, ssi=None, db=None) -> int:
    if ssi is None and db is None:
        return run_index_daily_ingest(date, index_codes)["index_daily_count"]
    return sum(fetch_index_daily_with_clients(ssi or SSIApi(), db or SupabaseClient(), code, date)["clean_rows"] for code in (index_codes or []))
