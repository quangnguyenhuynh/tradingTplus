"""Provider-independent daily fetch boundary."""
from src.providers.ssi.base import DataSourceAdapter, AdapterResult


def fetch_daily_price(provider: DataSourceAdapter, symbol: str, date: str) -> AdapterResult:
    return provider.fetch("stock_daily", symbol, date)
