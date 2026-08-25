"""One-index DailyIndex fetch, raw preservation, mapping, validation, and clean write."""
from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.index_daily_fetcher import fetch_index_daily
from src.pipeline.index_daily_mapper import build_index_daily_record, build_index_raw_daily_record
from src.pipeline.index_daily_persistence import persist_index_daily, persist_index_raw_daily
from src.ssi.api import SSIApi
from src.validation.index_daily_validator import validate_index_daily_record


def fetch_index_daily_with_clients(ssi: SSIApi, db: SupabaseClient, index_code: str, date: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"index_code": index_code, "date": date, "raw_rows": 0, "clean_rows": 0, "rejected_rows": 0, "warning_count": 0, "errors": [], "status": "FAILED"}
    try:
        payloads = fetch_index_daily(ssi, index_code, date)
    except Exception as exc:
        summary["errors"].append(str(exc)); return summary
    if not payloads:
        summary["errors"].append(f"No DailyIndex data for {index_code} on {date}"); return summary
    raw_records = [build_index_raw_daily_record(index_code, date, payload) for payload in payloads]
    persist_index_raw_daily(db, raw_records)
    summary["raw_rows"] = len(raw_records)
    for payload in payloads:
        clean = build_index_daily_record(index_code, date, payload)
        if clean is None:
            summary["rejected_rows"] += 1
            summary["errors"].append("Payload index code/date is missing or outside requested scope")
            continue
        validation = validate_index_daily_record(clean)
        summary["warning_count"] += len(validation.warnings)
        if not validation.is_valid:
            summary["rejected_rows"] += 1
            summary["errors"].extend(issue.message for issue in validation.errors)
            continue
        persist_index_daily(db, clean); summary["clean_rows"] += 1
    summary["status"] = "OK" if summary["clean_rows"] and not summary["rejected_rows"] else "PARTIAL" if summary["clean_rows"] else "FAILED"
    return summary
