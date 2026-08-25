"""SSI DailyIndex fetch boundary."""
from src.ssi.api import SSIApi


def fetch_index_daily(ssi: SSIApi, index_code: str, date: str) -> list[dict]:
    return ssi.get_daily_index_items(index_code, date)
