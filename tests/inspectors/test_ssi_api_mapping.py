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


def test_v3_dictionary_preserves_raw_and_existing_clean_contract():
    before = copy.deepcopy(FIXTURE)
    clean, reports = mapped("ssi_v3", "securities-summary", FIXTURE["data"], PARAMS)
    assert set(clean[0]) == set(get_contract("stock_daily")["fields"])
    assert clean[0]["average_price"] == 21106
    assert clean[0]["foreign_current_room"] == 1750293719
    assert clean[0]["foreign_buy_vol_total"] == 0
    assert clean[0]["total_match_vol"] is None
    assert "total_match_vol" in reports[0]["unsupported_fields"]
    assert "summary.totalMatch" in reports[0]["unused_source_fields"]
    assert FIXTURE == before


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
    if name.startswith(("src.database", "src.pipeline", "src.features", "src.data_preview", "supabase")):
        raise AssertionError("unexpected dependency: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
sys.argv = ["inspect.py", "list"]
runpy.run_path("scripts/ssi_api_inspector/inspect.py", run_name="__main__")
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ssi_v3" in result.stdout
