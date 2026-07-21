"""SSI fetch operations used by the intraday ingest pipeline."""
from src.ssi.api import SSIApi


def fetch_intraday_candles(ssi: SSIApi, symbol: str, date: str) -> list[dict]:
    """Fetch SSI IntradayOhlc resolution 1 without transforming data."""
    return ssi.get_intraday(symbol, date) or []
