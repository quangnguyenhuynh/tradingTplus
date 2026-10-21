"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def run_intraday_ingest(date: str | None = None, symbols: list[str] | tuple[str, ...] | None = None, data_source: str | None = None) -> dict[str, Any]:
    raise CapabilityUnavailableError("stock_intraday")
