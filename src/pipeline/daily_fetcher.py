"""SSI fetch operations used by the daily ingest pipeline."""
from src.ssi.api import SSIApi


def fetch_daily_price(ssi: SSIApi, symbol: str, date: str) -> dict | None:
    """Fetch one DailyStockPrice payload without mapping or persistence."""
    return ssi.get_daily_price(symbol, date)
