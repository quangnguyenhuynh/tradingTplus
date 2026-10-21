"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def fetch_intraday_candles(ssi: Any, symbol: str, date: str) -> list[dict]:
    raise CapabilityUnavailableError("stock_intraday")
