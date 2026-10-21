"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def run_stock_intraday_pipeline(date: str | None = None, *, symbols=None, data_source: str | None = None) -> dict:
    raise CapabilityUnavailableError("stock_intraday")
