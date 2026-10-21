"""Verified v3 mapping and service boundary parity."""
from types import SimpleNamespace
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.ingest.stock_daily.daily_mapper import build_stock_daily_record
from src.ingest.stock_daily.daily_service import fetch_daily_for_symbol_with_clients


def test_stock_daily_helper_matches_provider_mapping():
    payload = {"symbol": "SSI", "tradingDate": "2026/06/18", "open": 10, "high": 11,
               "low": 9, "close": 10.5, "totalTradedVolume": 100, "totalTradedValue": 1050}
    provider = SSIV3Adapter(SimpleNamespace(securities_summary=lambda *_: SimpleNamespace(items=[payload])))
    assert build_stock_daily_record("SSI", "18/06/2026", payload) == provider.fetch("stock_daily", "SSI", "18/06/2026").clean[0]


def test_mapping_error_preserves_raw_but_blocks_clean():
    calls = []
    provider = SSIV3Adapter(SimpleNamespace(securities_summary=lambda *_: SimpleNamespace(items=[
        {"symbol": "SSI", "tradingDate": "2026/06/18", "open": True}])))
    db = SimpleNamespace(upsert_raw_daily=lambda rows: calls.append("raw"),
                         upsert_stock_daily=lambda rows: calls.append("clean"))
    result = fetch_daily_for_symbol_with_clients(provider, db, "SSI", "18/06/2026")
    assert calls == ["raw"] and result["daily_rows"] == 0
    assert result["mapping_report"]["record_reports"][0]["transform_errors"]
