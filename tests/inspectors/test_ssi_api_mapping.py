"""Inspector integration using stored payloads and synthetic edge cases, never live APIs."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ssi_api_inspector import inspect
from scripts.ssi_api_inspector.client import InspectorResponse
from scripts.ssi_api_inspector.endpoints import V2_ENDPOINTS, V3_ENDPOINTS
from scripts.ssi_api_inspector.mapping import endpoint_mapping, map_rows
from src.data_contracts import get_contract

FIXTURE = json.loads(Path("tests/fixtures/data_preview/ssi_v3_securities_summary_ssi_2026-09-08.json").read_text())
PARAMS = {"symbol": "SSI", "from": "2026/09/08", "to": "2026/09/08"}


def response(body, status=200):
    return InspectorResponse(status, .1, "application/json", body, "json", "json", "https://api.ssi.com.vn/test", {})


def mapped(source, endpoint, rows, params):
    dataset, mapping = endpoint_mapping(source, endpoint)
    return map_rows(source, dataset, mapping, rows, params)


def test_v3_stock_daily_complete_response_preserves_raw_and_maps_confirmed_fields():
    before = copy.deepcopy(FIXTURE)
    clean, reports = mapped("ssi_v3", "securities-summary", FIXTURE["data"], PARAMS)
    assert set(clean[0]) == set(get_contract("stock_daily")["fields"]) | {"foreign_total_room"}
    assert clean[0] == {
        "symbol": "SSI", "trading_date": "2026-09-08", "price_change": 150.0,
        "per_price_change": .72, "ceiling_price": None, "floor_price": None,
        "ref_price": None, "open_price": 20850.0, "highest_price": 21300.0,
        "lowest_price": 20850.0, "close_price": 21000.0,
        "average_price": 21106.0, "foreign_buy_vol_total": 0,
        "foreign_sell_vol_total": 0, "foreign_buy_val_total": 0,
        "foreign_sell_val_total": 0, "foreign_current_room": 1750293719,
        "close_price_adjusted": None, "total_match_vol": 13825100.0,
        "total_match_val": 291796245000.0, "total_deal_vol": None,
        "total_deal_val": None, "total_traded_vol": None,
        "total_traded_value": None, "net_foreign_vol": None,
        "net_foreign_val": None, "total_buy_trade": 10133.0,
        "total_buy_trade_vol": 25665273.0, "total_sell_trade": 8430.0,
        "total_sell_trade_vol": 26176737.0, "foreign_total_room": None,
    }
    assert not reports[0]["errors"]
    assert "total_match_vol" not in reports[0]["unsupported_fields"]
    assert "summary.totalMatch" not in reports[0]["unused_source_fields"]
    assert FIXTURE == before


def test_v3_stock_daily_null_average_zero_foreign_and_missing_optional_are_preserved():
    row = {**FIXTURE["data"][0], "average": None, "totalForeignBuy": "0"}
    row.pop("totalDealValue")
    clean, reports = mapped("ssi_v3", "securities-summary", [row], PARAMS)
    assert clean[0]["average_price"] is None
    assert clean[0]["foreign_buy_vol_total"] == 0
    assert clean[0]["total_deal_val"] is None
    assert not reports[0]["errors"]


def test_v3_stock_daily_buy_sell_deal_and_distinct_room_mappings():
    row = {
        **FIXTURE["data"][0], "totalBuy": "11", "totalTradeBuy": "1200",
        "totalSell": "9", "totalTradeSell": "800", "totalDeal": "50",
        "totalDealValue": "750000", "remainForeignRoom": "1234",
        "totalForeignRoom": "5678",
    }
    clean, reports = mapped("ssi_v3", "securities-summary", [row], PARAMS)
    assert clean[0]["total_buy_trade"] == 11
    assert clean[0]["total_buy_trade_vol"] == 1200
    assert clean[0]["total_sell_trade"] == 9
    assert clean[0]["total_sell_trade_vol"] == 800
    assert clean[0]["total_deal_vol"] == 50
    assert clean[0]["total_deal_val"] == 750000
    assert clean[0]["foreign_current_room"] == 1234
    assert clean[0]["foreign_total_room"] == 5678
    assert not reports[0]["errors"]


def test_v2_range_uses_each_payload_date_and_does_not_overwrite_raw():
    raw = [{"symbol": "SSI", "tradingdate": day, "closeprice": "21000"}
           for day in ("07/09/2026", "08/09/2026")]
    before = copy.deepcopy(raw)
    clean, reports = mapped("ssi_v2", "daily-stock-price", raw,
                            {"Symbol": "SSI", "FromDate": "07/09/2026", "ToDate": "08/09/2026"})
    assert [row["trading_date"] for row in clean] == ["2026-09-07", "2026-09-08"]
    assert clean[0]["close_price"] == 21000 and not reports[0]["errors"]
    assert raw == before


@pytest.mark.parametrize("source,row,params", [
    ("ssi_v2", {"TradingDate": "08/09/2026", "Time": "09:15:00", "Close": "10.5", "Volume": "100"},
     {"Symbol": "SSI", "FromDate": "08/09/2026", "ToDate": "08/09/2026"}),
    ("ssi_v3", {"time": "2026/09/08 09:15:00", "close": "10.5", "volume": "100"}, PARAMS),
])
def test_intraday_uses_1m_source_time_and_existing_estimated_value(source, row, params):
    clean, reports = mapped(source, "intraday-ohlc", [row], params)
    assert clean[0]["time"] == "2026-09-08T02:15:00Z"
    assert clean[0]["timeframe"] == "1m" and clean[0]["value"] == 1050
    assert not reports[0]["errors"] and "value" not in reports[0]["missing_optional"]


@pytest.mark.parametrize("source,endpoint,row,params", [
    ("ssi_v2", "daily-index", {"IndexId": "VNINDEX", "TradingDate": "08/09/2026", "IndexValue": "1280.5"},
     {"IndexId": "VNINDEX", "FromDate": "08/09/2026", "ToDate": "08/09/2026"}),
    ("ssi_v3", "index-summary", {"index": "VNINDEX", "tradingDate": "2026/09/08", "indexValue": "1280.5"},
     {"index": "VNINDEX", "tradingDate": "2026/09/08"}),
])
def test_index_maps_into_existing_fields(source, endpoint, row, params):
    clean, reports = mapped(source, endpoint, [row], params)
    assert clean[0]["index_code"] == "VNINDEX" and clean[0]["index_value"] == 1280.5
    assert set(clean[0]) == set(get_contract("index_daily")["fields"])
    assert not reports[0]["errors"]


@pytest.mark.parametrize("changes", [{"symbol": "HPG"}, {"tradingDate": "2026/09/07"},
                                     {"close": "bad"}, {"averagePrice": "1"}])
def test_bad_identity_date_number_or_alias_fails_without_changing_raw(changes, capsys):
    row = {**FIXTURE["data"][0], **changes}
    body = {"data": [row]}
    before = copy.deepcopy(body)
    status = inspect.print_report("ssi_v3", V3_ENDPOINTS["securities-summary"], PARAMS,
                                  response(body), limit=1, full_json=True)
    out = capsys.readouterr().out
    assert status == "FAILED" and "Full raw JSON" in out and "Mapping status: FAILED" in out
    assert body == before


def test_missing_date_in_v2_range_is_not_invented_and_missing_stays_null():
    clean, reports = mapped("ssi_v2", "daily-stock-price", [{"Symbol": "SSI"}],
                            {"Symbol": "SSI", "FromDate": "07/09/2026", "ToDate": "08/09/2026"})
    assert clean == [None] and "trading_date" in reports[0]["missing_required"]
    clean, reports = mapped("ssi_v3", "securities-summary", [{"symbol": "SSI", "tradingDate": "2026/09/08"}], PARAMS)
    assert clean[0]["close_price"] is None and clean[0]["foreign_buy_vol_total"] is None


@pytest.mark.parametrize("source,endpoint,body", [
    ("ssi_v3", "daily-stock-price", FIXTURE),
    ("ssi_v2", "daily-stock-price", {"dataList": [{"Symbol": "SSI", "TradingDate": "08/09/2026", "ClosePrice": "21000"}]}),
])
def test_cli_fetches_once_and_prints_raw_clean_and_optional_rules(source, endpoint, body, monkeypatch, capsys):
    calls = []
    class Client:
        token = None
        def __init__(self, data_source, **kwargs):
            assert data_source == source
        def request_endpoint(self, endpoint, params, post_json=None):
            calls.append(params)
            return response(copy.deepcopy(body))
    monkeypatch.setattr(inspect, "InspectorClient", Client)
    argv = ["run", endpoint, "--symbol", "SSI", "--date", "08/09/2026", "--full-json", "--show-mapping"]
    if source == "ssi_v2":
        argv += ["--data-source", source]
    assert inspect.main(argv) == 0
    out = capsys.readouterr().out
    assert len(calls) == 1
    assert "Full raw JSON" in out and "Full clean JSON" in out and "Mapping rules" in out
    assert '"close_price": 21000.0' in out and "NO DATABASE WRITES" in out
    if source == "ssi_v3":
        assert "Inspector-only preview mappings (not persisted)" in out
        assert '"foreign_total_room"' in out and "DB COLUMN NOT YET CREATED" in out
    assert "securities-summary" in out if source == "ssi_v3" else "daily-stock-price" in out


def test_bad_record_outside_sample_still_fails_and_full_json_includes_all(capsys):
    body = {"data": [FIXTURE["data"][0], {**FIXTURE["data"][0], "close": "bad"}]}
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["securities-summary"], PARAMS,
                                response(body), limit=1, full_json=False) == "FAILED"
    assert '"close_price": 21000.0' in capsys.readouterr().out
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["securities-summary"], PARAMS,
                                response(body), limit=1, full_json=True) == "FAILED"
    assert '"close": "bad"' in capsys.readouterr().out


def test_error_empty_and_unsupported_endpoints_never_fabricate_clean(capsys):
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["securities-summary"], PARAMS,
                                response({"msg": "bad request"}, 400), limit=1, full_json=True) == "FAILED"
    assert "Clean mapping: skipped" in capsys.readouterr().out
    assert inspect.print_report("ssi_v3", V3_ENDPOINTS["securities-summary"], PARAMS,
                                response({"data": []}), limit=1, full_json=True) == "EMPTY"
    assert "Full clean JSON:\n[]" in capsys.readouterr().out
    assert endpoint_mapping("ssi_v3", "daily-ohlc") is None


def test_inspector_imports_and_runs_without_database_or_pipeline():
    script = '''
import builtins
import runpy
import sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(("src.database", "src.pipeline", "src.features", "supabase")):
        raise AssertionError("unexpected dependency: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
sys.argv = ["inspect.py", "list"]
runpy.run_path("scripts/ssi_api_inspector/inspect.py", run_name="__main__")
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ssi_v3" in result.stdout


@pytest.mark.parametrize(("source", "dataset", "row", "identity"), [
    ("ssi_v2", "symbol_list", {"Symbol": "SSI", "StockName": "SSI Securities", "Market": "HOSE", "Extra": 7}, "symbol"),
    ("ssi_v3", "symbol_list", {"symbol": "SSI", "unknown": True}, "symbol"),
    ("ssi_v2", "index_list", {"IndexCode": "VNINDEX", "IndexName": "VN Index", "Exchange": "HOSE"}, "index_code"),
    ("ssi_v3", "index_list", {"index": "VNINDEX", "unknown": True}, "index_code"),
])
def test_catalog_mapping_preserves_raw_and_maps_verified_identity(source, dataset, row, identity):
    from src.data_contracts.registry import get_mapping
    before = copy.deepcopy(row)
    clean, reports = map_rows(source, dataset, get_mapping(source, dataset), [row], {})
    assert clean[0][identity] in {"SSI", "VNINDEX"}
    assert row == before and not reports[0]["errors"]


def test_catalog_missing_and_duplicate_identity_are_traceable_outside_sample(capsys):
    body = {"data": [{"Symbol": "SSI"}, {"Symbol": ""}, {"Symbol": "ssi"}]}
    status = inspect.print_report("ssi_v2", V2_ENDPOINTS["securities"], {"Market": "HOSE"},
                                  response(body), limit=1, full_json=False,
                                  dataset="symbol_list", requested_source="ssi_v2",
                                  source_status="preview", paging_supported=True)
    output = capsys.readouterr().out
    assert status == "FAILED"
    assert "MISSING_REQUIRED" in output and "DUPLICATE_IDENTITY" in output
