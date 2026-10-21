"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def run_refill_pipeline(from_date: str, to_date: str, symbol: str, data_source: str | None = None) -> dict[str, Any]:
    raise CapabilityUnavailableError("stock_intraday")
