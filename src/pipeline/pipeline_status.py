"""Shared source-pipeline status helpers."""
from __future__ import annotations

from typing import Any


def validate_pipeline_summary(summary: Any, name: str) -> list[str]:
    if not isinstance(summary, dict):
        return [f"{name} returned non-dict summary"]
    symbol_count = int(summary.get("symbol_count") or 0)
    error_count = int(summary.get("error_count") or len(summary.get("errors") or []))
    if summary.get("status") == "FAILED" or (symbol_count > 0 and error_count >= max(1, symbol_count)):
        return [f"{name} failed for all symbols ({error_count}/{symbol_count})"]
    return []


def status_from_ingest(summary: dict[str, Any], failures: list[str], warnings: list[str]) -> str:
    ingest_status = summary.get("status")
    if int(summary.get("stock_daily_count") or 0) == 0:
        failures.append("stock_daily_count == 0")
    if int(summary.get("stock_intraday_count") or 0) == 0:
        failures.append("stock_intraday_count == 0")
    if ingest_status == "FAILED" and "ingest completeness status FAILED" not in failures:
        failures.append("ingest completeness status FAILED")
    if failures:
        return "FAILED"
    if ingest_status == "PARTIAL" or summary.get("missing_stock_daily_count", 0) or summary.get("missing_intraday_count", 0) or summary.get("incomplete_intraday_count", 0):
        warnings.append("ingest completeness is partial")
        return "PARTIAL"
    return "OK"
