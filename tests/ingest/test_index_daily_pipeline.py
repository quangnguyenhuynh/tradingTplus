from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.pipeline.index_daily_mapper import build_index_daily_record, build_index_raw_daily_record
from src.pipeline.index_daily_persistence import _validate_index_raw_daily_row
from src.pipeline.index_daily_service import fetch_index_daily_with_clients
from src.pipeline.index_scope import normalize_index_scope, resolve_index_scope
from src.pipeline.date_utils import parse_index_date
from src.validation.index_daily_validator import validate_index_daily_record


PAYLOAD = {"IndexId": "VNINDEX", "TradingDate": "25/08/2026", "IndexValue": 1280.5, "TotalMatchVol": 10, "TotalDealVol": 2, "TotalVol": 12}


@pytest.mark.parametrize("value", ["2026-08-24", "24/08/2026"])
def test_shared_index_date_parser_accepts_documented_formats(value):
    assert parse_index_date(value).iso == "2026-08-24"


def test_shared_index_date_parser_rejects_other_separators():
    with pytest.raises(ValueError, match="YYYY-MM-DD or DD/MM/YYYY"):
        parse_index_date("24-08-2026")


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


def test_valid_response_persists_raw_then_clean_without_downstream_work():
    calls = []
    class SSI:
        def get_daily_index_items(self, code, date): return [PAYLOAD]
    class DB:
        def upsert_index_raw_daily(self, rows): calls.append(("raw", rows))
        def upsert_index_daily(self, rows): calls.append(("clean", rows))

    summary = fetch_index_daily_with_clients(SSI(), DB(), "VNINDEX", "25/08/2026")

    assert summary["status"] == "OK"
    assert summary["raw_rows"] == summary["clean_rows"] == 1
    assert [name for name, _ in calls] == ["raw", "clean"]
    created_at = calls[0][1][0]["created_at"]
    assert datetime.fromisoformat(created_at).utcoffset() == timedelta(0)
    assert "created_at" not in calls[0][1][0]["payload"]


def test_repository_boundary_sends_complete_batch_with_one_utc_ingestion_timestamp():
    """Capture the exact mapper -> persistence -> DatabaseClient input."""
    calls = []

    class SSI:
        def get_daily_index_items(self, code, date):
            return [PAYLOAD, {**PAYLOAD, "TradingSession": "CLOSE"}]

    class RecordingDatabaseClient:
        def upsert_index_raw_daily(self, rows):
            calls.append(("index_raw_daily", rows))

        def upsert_index_daily(self, rows):
            calls.append(("index_daily", rows))

    summary = fetch_index_daily_with_clients(
        SSI(), RecordingDatabaseClient(), "VNINDEX", "25/08/2026"
    )

    table, rows = calls[0]
    assert table == "index_raw_daily"
    assert rows
    assert summary["raw_rows"] == summary["clean_rows"] == 2
    timestamps = {row["created_at"] for row in rows}
    assert len(timestamps) == 1
    for row in rows:
        assert "created_at" in row
        assert row["created_at"] is not None
        parsed = datetime.fromisoformat(row["created_at"])
        assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)
        assert "created_at" not in row["payload"]


def test_raw_audit_validation_fails_before_database_request_with_safe_context():
    with pytest.raises(
        ValueError,
        match=(
            "index_raw_daily row missing required created_at: "
            "index_code=VNINDEX, trading_date=2026-08-24"
        ),
    ):
        _validate_index_raw_daily_row(
            {"index_code": "VNINDEX", "trading_date": "2026-08-24"}
        )


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
