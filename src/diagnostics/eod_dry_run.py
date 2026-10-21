"""Unavailable ingestion boundary; no API or database access."""
from __future__ import annotations
from typing import Any
from src.providers.ssi.capabilities import CapabilityUnavailableError

def _build_symbol_summary(ssi: Any, date: str, symbol: str, timeframes: list[str]) -> dict[str, Any]:
    raise CapabilityUnavailableError("stock_intraday")

def run_eod_dry_run(
    date: str | None,
    symbols: list[str] | None,
    timeframes: list[str] | None,
    json_output: bool = False,
) -> dict[str, Any]:
    raise CapabilityUnavailableError("stock_intraday")
