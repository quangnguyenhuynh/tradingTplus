"""Only the explicitly scoped manual pilot is available; no automatic ingest."""
from __future__ import annotations

def run_stock_intraday_pipeline(date: str | None = None, *, symbols=None, data_source: str | None = None,
                                write: bool = False) -> dict:
    from src.ingest.stock_intraday.manual import run_manual_intraday

    return run_manual_intraday(date, symbols=symbols, data_source=data_source, write=write)
