"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def fetch_one_day_with_clients(ssi: Any, db: SupabaseClient, symbol: str, date: str) -> int:
    raise CapabilityUnavailableError("stock_intraday")

def fetch_one_day(symbol: str, date: str) -> int:
    raise CapabilityUnavailableError("stock_intraday")
