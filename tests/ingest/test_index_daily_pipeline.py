from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.database.client import SupabaseClient
from src.data_sources.ssi_v3 import SSIV3Adapter
from src.pipeline.index_daily_mapper import build_index_daily_record, build_index_raw_daily_record
from src.pipeline.index_daily_persistence import _validate_index_raw_daily_row
from src.pipeline.index_daily_service import fetch_index_daily_with_clients
from src.pipeline.index_scope import normalize_index_scope, resolve_index_scope
from src.pipeline.date_utils import parse_index_date
from src.validation.index_daily_validator import validate_index_daily_record
from src.ssi.v3 import SSIV3Client


PAYLOAD = {"IndexId": "VNINDEX", "TradingDate": "25/08/2026", "IndexValue": 1280.5, "TotalMatchVol": 10, "TotalDealVol": 2, "TotalVol": 12}

FULL_PAYLOAD = {
    "Indexcode": "VNINDEX", "IndexValue": "1280.50", "TradingDate": "25/08/2026",
    "Time": "", "Change": -1.25, "RatioChange": "-0.0975", "TotalTrade": "1234",
    "Totalmatchvol": 1_000_001, "Totalmatchval": "25000000001.5", "TypeIndex": "Market",
    "IndexName": "VN Index", "Advances": "180", "Nochanges": 20, "Declines": "100",
    "Ceiling": 4, "Floor": "3", "Totaldealvol": "2000", "Totaldealval": 3000000,
    "Totalvol": "1002001", "Totalval": 25003000001.5, "TradingSession": "CLOSE",
    "Market": "HOSE", "Exchange": "HOSE",
}

V3_PAYLOAD = {
    "tradingDate": "2026/08/25", "totalTrade": "100", "totalTradeValue": "1000",
    "totalMatch": "90", "totalMatchValue": "900", "totalDeal": "10",
    "totalDealValue": "100", "indexChange": "10.02",
    "indexChangePercentage": "0.75", "indexValue": "1280.50",
    "totalAdvanceStock": "180", "totalCeilingStock": "4",
    "totalDeclineStock": "100", "totalFloorStock": "3", "totalNoChangeStock": "20",
    "totalPropBuy": "11", "totalPropBuyValue": "12", "totalPropSell": "13",
    "totalPropSellValue": "14", "totalBuyForeign": "15",
    "totalBuyForeignValue": "16", "totalSellForeign": "17",
    "totalSellForeignValue": "18", "netPurchasesForeignVolume": "-2",
    "netPurchasesForeignValue": "-2", "futureField": {"untouched": True},
}


def test_v3_adapter_maps_all_verified_fields_without_scaling_and_preserves_raw():
    before = dict(V3_PAYLOAD)
    client = SimpleNamespace(index_summary=lambda *_: SimpleNamespace(items=[V3_PAYLOAD]))
    result = SSIV3Adapter(client).fetch("index_daily", "VNINDEX", "25/08/2026")
    clean = result.clean[0]
    assert result.raw[0] == before == V3_PAYLOAD
    assert clean["index_code"] == "VNINDEX"
    assert clean["index_change"] == 10.02
    assert clean["index_change"] != 0.1002
    assert clean["index_change_percentage"] == 0.75
    assert clean["net_foreign_purchase_volume"] == -2
    assert set(clean) == {
        "index_code", "trading_date", "index_value", "index_change", "index_change_percentage",
        "total_trade_volume", "total_trade_value", "total_match_volume", "total_match_value",
        "total_deal_volume", "total_deal_value", "total_advance_stock", "total_ceiling_stock",
        "total_decline_stock", "total_floor_stock", "total_no_change_stock",
        "total_prop_buy_volume", "total_prop_buy_value", "total_prop_sell_volume",
        "total_prop_sell_value", "total_foreign_buy_volume", "total_foreign_buy_value",
        "total_foreign_sell_volume", "total_foreign_sell_value",
        "net_foreign_purchase_volume", "net_foreign_purchase_value",
    }


def test_v3_adapter_keeps_missing_optional_values_null():
    client = SimpleNamespace(index_summary=lambda *_: SimpleNamespace(items=[{"tradingDate": "2026/08/25"}]))
    clean = SSIV3Adapter(client).fetch("index_daily", "VNINDEX", "2026-08-25").clean[0]
    assert clean["index_value"] is None
    assert clean["total_foreign_buy_value"] is None


def test_v3_client_uses_verified_index_summary_request(monkeypatch):
    client = SSIV3Client.__new__(SSIV3Client)
    calls = []
    monkeypatch.setattr(client, "_request", lambda method, path, **kwargs: calls.append((method, path, kwargs)) or {"data": []})
    result = client.index_summary("VNINDEX", "25/08/2026")
    assert result.items == []
    assert calls == [("GET", "/data/indexSummary", {"params": {"index": "VNINDEX", "tradingDate": "2026/08/25"}})]


def test_index_daily_writer_uses_composite_primary_key_conflict_target(monkeypatch):
    captured = []
    db = object.__new__(SupabaseClient)
    monkeypatch.setattr(
        db,
        "_upsert_in_batches",
        lambda table, rows, **kwargs: captured.append((table, rows, kwargs)),
    )
    rows = [
        {"index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": 1},
        {"index_code": "HNXINDEX", "trading_date": "2026-08-25", "index_value": 2},
    ]

    db.upsert_index_daily(rows)

    assert captured == [
        ("index_daily", rows, {"on_conflict": "index_code,trading_date"})
    ]


@pytest.mark.parametrize("value", ["2026-08-24", "24/08/2026"])
def test_shared_index_date_parser_accepts_documented_formats(value):
    assert parse_index_date(value).iso == "2026-08-24"


def test_shared_index_date_parser_rejects_other_separators():
    with pytest.raises(ValueError, match="YYYY-MM-DD or DD/MM/YYYY"):
        parse_index_date("24-08-2026")


def test_mapper_uses_payload_identity_and_keeps_missing_nullable():
    record = build_index_daily_record("VNINDEX", "25/08/2026", PAYLOAD)
    assert record["trading_date"] == "2026-08-25"
    assert record["total_trade_value"] is None
    assert "raw" not in record
    assert build_index_daily_record("VN30", "25/08/2026", PAYLOAD) is None


def test_raw_mapper_preserves_mismatched_payload_with_deterministic_hash():
    first = build_index_raw_daily_record("VN30", "25/08/2026", PAYLOAD)
    second = build_index_raw_daily_record("VN30", "25/08/2026", dict(PAYLOAD))
    assert first["index_code"] == "VNINDEX"
    assert first["data_hash"] == second["data_hash"]


@pytest.mark.parametrize("time_value", [None, ""])
def test_all_documented_fields_are_preserved_raw_and_promoted_when_selected(time_value):
    payload = {**FULL_PAYLOAD, "Time": time_value}
    raw = build_index_raw_daily_record("VNINDEX", "25/08/2026", payload)
    clean = build_index_daily_record("VNINDEX", "25/08/2026", payload)

    assert len(payload) == 23
    assert raw["payload"] == payload
    assert clean["index_code"] == "VNINDEX"
    assert clean["trading_date"] == "2026-08-25"
    assert clean["index_change"] == -1.25
    assert clean["index_change_percentage"] == -0.0975
    assert clean["total_trade_volume"] == 1002001.0
    assert clean["total_match_value"] == 25000000001.5
    assert clean["total_no_change_stock"] == 20.0
    assert clean["total_prop_buy_volume"] is None
    assert "index_name" not in clean


@pytest.mark.parametrize(
    ("ceiling_key", "floor_key", "no_changes_key"),
    [("Ceiling", "Floor", "Nochanges"), ("Ceilings", "Floors", "NoChanges")],
)
def test_market_breadth_aliases(ceiling_key, floor_key, no_changes_key):
    payload = {
        "indexid": "VNINDEX", "TradingDate": "25/08/2026",
        ceiling_key: "5", floor_key: 6, no_changes_key: "7",
    }
    clean = build_index_daily_record("VNINDEX", "25/08/2026", payload)
    assert clean["total_ceiling_stock"] == 5.0
    assert clean["total_floor_stock"] == 6.0
    assert clean["total_no_change_stock"] == 7.0


def test_missing_numeric_fields_remain_null_not_zero():
    clean = build_index_daily_record(
        "VNINDEX", "25/08/2026", {"Indexcode": "VNINDEX", "TradingDate": "25/08/2026"}
    )
    assert clean["index_value"] is None
    assert clean["total_trade_volume"] is None
    assert clean["total_ceiling_stock"] is None


def test_validator_rejects_impossible_and_warns_on_component_difference():
    bad = validate_index_daily_record({"index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": -1})
    assert not bad.is_valid
    warning = validate_index_daily_record({"index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": 1, "total_trade_volume": 99, "total_match_volume": 1, "total_deal_volume": 1})
    assert warning.is_valid and warning.warnings
    foreign = validate_index_daily_record({
        "index_code": "VNINDEX", "trading_date": "2026-08-25", "index_value": 1,
        "total_foreign_buy_volume": 10, "total_foreign_sell_volume": 12,
        "net_foreign_purchase_volume": -1,
    })
    assert foreign.is_valid
    assert [item.code for item in foreign.warnings] == ["INDEX_FOREIGN_NET_MISMATCH"]


def test_v3_service_labels_raw_evidence_and_writes_no_features():
    calls = []
    client = SimpleNamespace(index_summary=lambda *_: SimpleNamespace(items=[V3_PAYLOAD]))
    class DB:
        def upsert_index_raw_daily(self, rows): calls.append(("raw", rows))
        def upsert_index_daily(self, rows): calls.append(("clean", rows))
    summary = fetch_index_daily_with_clients(SSIV3Adapter(client), DB(), "VNINDEX", "25/08/2026")
    assert summary["status"] == "OK"
    assert [name for name, _ in calls] == ["raw", "clean"]
    assert calls[0][1][0]["source"] == "SSI_v3_indexSummary"
    assert calls[0][1][0]["payload"] == V3_PAYLOAD


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
        def get_daily_index_items(self, code, date): return [FULL_PAYLOAD]
    class DB:
        def upsert_index_raw_daily(self, rows): calls.append(("raw", rows))
        def upsert_index_daily(self, rows): calls.append(("clean", rows))

    summary = fetch_index_daily_with_clients(SSI(), DB(), "VNINDEX", "25/08/2026")

    assert summary["status"] == "OK"
    assert summary["raw_rows"] == summary["clean_rows"] == 1
    assert [name for name, _ in calls] == ["raw", "clean"]
    created_at = calls[0][1][0]["created_at"]
    assert datetime.fromisoformat(created_at).utcoffset() == timedelta(0)
    assert calls[0][1][0]["payload"] == FULL_PAYLOAD
    assert calls[1][1][0]["total_match_value"] == 25000000001.5
    assert calls[1][1][0]["total_ceiling_stock"] == 4.0
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


def test_omitted_index_scope_reads_only_active_master_rows():
    calls = []

    class Query:
        def select(self, *_): return self
        def eq(self, column, value):
            calls.append((column, value)); return self
        def order(self, *_): return self
        def execute(self): return SimpleNamespace(data=[{"index_code": "VNINDEX"}])

    db = SimpleNamespace(
        client=SimpleNamespace(table=lambda *_: Query()),
        _with_retry=lambda fn, **_: fn(),
    )

    assert resolve_index_scope(db, None) == (["VNINDEX"], None)
    assert calls == [("status", "active")]
