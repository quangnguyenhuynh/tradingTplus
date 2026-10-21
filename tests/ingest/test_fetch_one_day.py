import pytest
from src.providers.ssi.capabilities import CapabilityUnavailableError

class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected service access: {name}")

from datetime import datetime
from zoneinfo import ZoneInfo
from src.diagnostics.fetch_one_day import fetch_one_day, fetch_one_day_with_clients
from src.ingest.stock_intraday.intraday_mapper import parse_time, deduplicate_intraday_records
from src.ingest.stock_intraday.intraday_persistence import save_intraday_records
from src.intraday_value import calculate_trade_value


def test_time_helper_keeps_aware_market_timestamp_and_rejects_invalid():
    assert parse_time("18/06/2026", "09:15:00") == datetime(2026, 6, 18, 2, 15, tzinfo=ZoneInfo("UTC"))
    assert parse_time("18/06/2026", "25:00:00") is None


def test_estimated_value_preserves_missing_and_uses_candle_volume():
    assert calculate_trade_value(10.5, 100) == 1050
    assert calculate_trade_value(None, 100) is None
    assert calculate_trade_value(10.5, None) is None


def test_canonical_dedup_keeps_last_record_per_identity():
    a = {"symbol":"SSI", "timeframe":"1m", "time":"2026-06-18T02:15:00Z", "close":10}
    b = {**a, "close":11}
    assert deduplicate_intraday_records([a, b]) == [b]


def test_persistence_interface_keeps_raw_clean_separate():
    calls = []
    class DB:
        def upsert_raw(self, rows): calls.append(("raw", rows))
        def upsert_intraday(self, rows): calls.append(("clean", rows))
    raw, clean = [{"payload":{"original":1}}], [{"symbol":"SSI", "timeframe":"1m"}]
    assert save_intraday_records(DB(), raw, clean) == 1
    assert calls == [("raw",raw),("clean",clean)]


def test_combined_fetch_never_touches_injected_services():
    with pytest.raises(CapabilityUnavailableError):
        fetch_one_day_with_clients(Untouchable(), Untouchable(), "SSI", "19/10/2026")
    with pytest.raises(CapabilityUnavailableError):
        fetch_one_day("SSI", "19/10/2026")
