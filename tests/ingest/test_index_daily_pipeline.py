from types import SimpleNamespace

import pytest

from src.pipeline.index_daily_mapper import build_index_daily_record, build_index_raw_daily_record
from src.pipeline.index_daily_service import fetch_index_daily_with_clients
from src.pipeline.index_scope import normalize_index_scope, resolve_index_scope
from src.validation.index_daily_validator import validate_index_daily_record


PAYLOAD = {"IndexId": "VNINDEX", "TradingDate": "25/08/2026", "IndexValue": 1280.5, "TotalMatchVol": 10, "TotalDealVol": 2, "TotalVol": 12}


def test_mapper_uses_payload_identity_and_keeps_missing_nullable():
    record = build_index_daily_record("VNINDEX", "25/08/2026", PAYLOAD)
    assert record["trading_date"] == "2026-08-25"
    assert record["total_val"] is None
    assert "raw" not in record
    assert build_index_daily_record("VN30", "25/08/2026", PAYLOAD) is None


def test_raw_mapper_preserves_mismatched_payload_with_deterministic_hash():
    first = build_index_raw_daily_record("VN30", "25/08/2026", PAYLOAD)
    second = build_index_raw_daily_record("VN30", "25/08/2026", dict(PAYLOAD))
    assert first["index_code"] == "VNINDEX"
    assert first["data_hash"] == second["data_hash"]


def test_validator_rejects_impossible_and_warns_on_component_difference():
    bad = validate_index_daily_record({"index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": -1})
    assert not bad.is_valid
    warning = validate_index_daily_record({"index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": 1, "total_vol": 99, "total_match_vol": 1, "total_deal_vol": 1})
    assert warning.is_valid and warning.warnings


def test_service_persists_raw_before_rejecting_clean():
    calls = []
    class SSI:
        def get_daily_index_items(self, code, date): return [PAYLOAD]
    class DB:
        def upsert_index_raw_daily(self, rows): calls.append(("raw", rows))
        def upsert_index_daily(self, rows): calls.append(("clean", rows))
    summary = fetch_index_daily_with_clients(SSI(), DB(), "VN30", "25/08/2026")
    assert summary["raw_rows"] == 1 and summary["clean_rows"] == 0
    assert [name for name, _ in calls] == ["raw"]


def test_index_scope_resolves_case_insensitively_and_rejects_unknown():
    class Query:
        def select(self, *_): return self
        def order(self, *_): return self
        def execute(self): return SimpleNamespace(data=[{"index_code": "HNXIndex"}, {"index_code": "VNINDEX"}])
    db = SimpleNamespace(client=SimpleNamespace(table=lambda *_: Query()), _with_retry=lambda fn, **_: fn())
    assert normalize_index_scope([" vnindex ", "VNINDEX", "hnxindex"]) == ["vnindex", "hnxindex"]
    assert resolve_index_scope(db, ["vnindex", "HNXINDEX"])[0] == ["VNINDEX", "HNXIndex"]
    with pytest.raises(ValueError, match="Unknown index"):
        resolve_index_scope(db, ["MISSING"])
