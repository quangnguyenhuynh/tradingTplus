"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def fetch_intraday_for_symbol_with_clients(ssi: Any, db: SupabaseClient, symbol: str, date: str, daily_context: dict | None = None) -> dict[str, Any]:
    raise CapabilityUnavailableError("stock_intraday")
