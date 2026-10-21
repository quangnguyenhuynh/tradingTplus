"""One-index index daily fetch, raw preservation, mapping, validation, and clean write."""
from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.ingest.index_daily.index_daily_fetcher import fetch_index_daily
from src.ingest.index_daily.index_daily_mapper import build_index_raw_daily_record
from src.ingest.index_daily.index_daily_persistence import persist_index_daily, persist_index_raw_daily
from src.providers.ssi.base import DataSourceAdapter
from src.quality.validators.index_daily_validator import validate_index_daily_record


def fetch_index_daily_with_clients(ssi: DataSourceAdapter, db: SupabaseClient, index_code: str, date: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"index_code": index_code, "date": date, "raw_rows": 0, "clean_rows": 0, "rejected_rows": 0, "warning_count": 0, "errors": [], "status": "FAILED"}
    try:
        adapted = fetch_index_daily(ssi, index_code, date)
        payloads = adapted.raw
    except Exception as exc:
        summary["errors"].append(str(exc)); return summary
    if not payloads:
        summary["errors"].append(f"No index daily data for {index_code} on {date}"); return summary
    raw_source = adapted.raw_source or adapted.source
    raw_records = [build_index_raw_daily_record(index_code, date, payload, source=raw_source) for payload in payloads]
    persist_index_raw_daily(db, raw_records)
    summary["raw_rows"] = len(raw_records)
    mapping_reports = []
    for position, payload in enumerate(payloads):
        clean = adapted.clean[position]
        mapping_report = adapted.mapping_report.get("record_reports", [{}])[position]
        mapping_reports.append(mapping_report)
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
    summary["mapping_report"] = adapted.mapping_report
    summary["status"] = "OK" if summary["clean_rows"] and not summary["rejected_rows"] else "PARTIAL" if summary["clean_rows"] else "FAILED"
    return summary
