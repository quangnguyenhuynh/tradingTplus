"""Provider-independent index fetch boundary."""
from src.providers.ssi.base import DataSourceAdapter, AdapterResult


def fetch_index_daily(provider: DataSourceAdapter, index_code: str, date: str) -> AdapterResult:
    return provider.fetch("index_daily", index_code, date)
