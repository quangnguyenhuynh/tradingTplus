"""Synthetic provider results test the boundary, not an implementation of a future provider."""
from types import SimpleNamespace
from src.providers.ssi.base import AdapterResult
from src.ingest.index_daily.index_daily_service import fetch_index_daily_with_clients


def test_index_raw_provenance_comes_from_adapter_result():
    raw = {"original": True}
    clean = {"index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": 1000}
    result = AdapterResult("synthetic", "index_daily", [raw], [clean],
                           mapping_report={"record_reports": [{}]}, raw_source="synthetic-evidence")
    writes = []
    provider = SimpleNamespace(fetch=lambda *args: result)
    db = SimpleNamespace(upsert_index_raw_daily=lambda rows: writes.append(("raw", rows)),
                         upsert_index_daily=lambda rows: writes.append(("clean", rows)))
    assert fetch_index_daily_with_clients(provider, db, "VNINDEX", "25/08/2026")["status"] == "OK"
    assert writes[0][1][0]["source"] == "synthetic-evidence"
    assert writes[0][1][0]["payload"] is raw
    assert writes[1][1][0] == clean
