import copy
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import main
from src.data_preview.service import render_preview, run_preview

FIXTURE = json.loads(Path("tests/fixtures/data_preview/ssi_v3_securities_summary_ssi_2026-09-08.json").read_text())

class V3:
    def __init__(self, items=None): self.body = copy.deepcopy(FIXTURE); self.items = copy.deepcopy(items if items is not None else self.body["data"])
    def securities_summary(self, symbol, date): return SimpleNamespace(items=self.items, raw_pages=[self.body], pages=1, complete=True)

class V2:
    def get_daily_price_items(self, symbol, day):
        return [{"Symbol": symbol, "TradingDate": day, "OpenPrice": "20850", "HighestPrice": "21300", "LowestPrice": "20850", "ClosePrice": "21000", "AveragePrice": "21106", "TotalMatchVol": "13825100", "TotalMatchVal": "291796245000"}]

def test_live_evidence_fixture_mapping_precision_states_and_raw_immutable():
    client = V3(); before = copy.deepcopy(client.body)
    result = run_preview("stock_daily", "SSI", "2026-09-08", client=client)
    assert result["status"] == "OK" and result["fetch"]["pagination_complete"] is True
    record = result["records"][0]; clean = record["clean"]
    assert clean["trading_date"] == "2026-09-08" and clean["average_price"] == 21106
    assert clean["foreign_current_room"] == 1750293719
    assert clean["foreign_buy_vol_total"] == 0
    mapping = {row["clean_field"]: row for row in record["mapping"]}
    assert mapping["foreign_buy_vol_total"]["raw_state"] == "PRESENT"
    assert "does not prove" in mapping["foreign_buy_vol_total"]["warning"]
    assert mapping["total_match_vol"]["status"] == "UNVERIFIED"
    assert any(row["raw_field"] == "summary.totalMatch" for row in record["unmapped_raw_fields"])
    assert client.body == before

def test_null_empty_missing_invalid_and_zero_are_distinct():
    row = copy.deepcopy(FIXTURE["data"][0]); row["average"] = ""; row["close"] = "bad"; row["totalForeignBuy"] = None; del row["totalForeignSell"]
    result = run_preview("stock_daily", "SSI", "2026-09-08", client=V3([row]))
    mapping = {x["clean_field"]: x for x in result["records"][0]["mapping"]}
    assert mapping["average_price"]["raw_state"] == "EMPTY"
    assert mapping["close_price"]["status"] == "INVALID"
    assert mapping["foreign_buy_vol_total"]["raw_state"] == "NULL"
    assert mapping["foreign_sell_vol_total"]["raw_state"] == "ABSENT"

def test_duplicate_wrong_identity_no_data_and_json_error_document():
    assert run_preview("stock_daily", "SSI", "2026-09-08", client=V3([]))["status"] == "NO_DATA"
    duplicate = run_preview("stock_daily", "SSI", "2026-09-08", client=V3(FIXTURE["data"] * 2))
    assert duplicate["status"] == "INVALID" and duplicate["diagnostics"][0]["code"] == "DUPLICATE_BUSINESS_KEY"
    wrong = copy.deepcopy(FIXTURE["data"]); wrong[0]["symbol"] = "HPG"
    assert run_preview("stock_daily", "SSI", "2026-09-08", client=V3(wrong))["status"] == "INVALID"
    class Broken:
        def securities_summary(self, *_): raise RuntimeError("HTTP failed")
    error = run_preview("stock_daily", "SSI", "2026-09-08", client=Broken())
    assert error["status"] == "ERROR" and json.loads(render_preview(error, "json"))["status"] == "ERROR"

def test_compare_signed_delta_statuses_and_only_diff_keeps_unverified():
    result = run_preview("stock_daily", "SSI", "2026-09-08", compare=("ssi_v2", "ssi_v3"), client=V3(), v2_factory=V2)
    by_field = {row["clean_field"]: row for row in result["comparison"]}
    assert by_field["close_price"]["status"] == "MATCH"
    assert by_field["total_match_vol"]["status"] == "UNVERIFIED"
    rendered = json.loads(render_preview(result, "json", only_diff=True))
    assert any(row["status"] == "UNVERIFIED" for row in rendered["comparison"])

def test_cli_show_mapping_help_conflicts_and_no_database_import(monkeypatch, capsys):
    monkeypatch.setattr(main, "run_preview", lambda *a, **k: run_preview(*a, **k, client=V3()))
    assert main.main(["data-preview", "stock-daily", "--symbol", "SSI", "--date", "2026-09-08", "--show-mapping", "--format", "json"]) == 0
    assert "mapping" in json.loads(capsys.readouterr().out)["records"][0]
    assert main.main(["data-preview", "stock-daily", "--symbol", "SSI", "--date", "bad"]) == 2
    assert main.main(["data-preview", "stock-daily", "--symbol", "SSI", "--date", "08/09/2026", "--compare", "ssi_v3", "ssi_v3"]) == 2


def test_cli_ddmmyyyy_preview_reports_provider_formatted_v3_params(monkeypatch, capsys):
    monkeypatch.setattr(main, "run_preview", lambda *a, **k: run_preview(*a, **k, client=V3()))
    assert main.main(["data-preview", "stock-daily", "--symbol", "SSI", "--date", "08/09/2026", "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["request"]["params"]["from"] == "2026/09/08"
    assert result["request"]["params"]["to"] == "2026/09/08"


def test_preview_module_has_no_database_or_persistence_import():
    tree = ast.parse(Path("src/data_preview/service.py").read_text())
    imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    imports += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any("database" in name or "persistence" in name for name in imports)


def test_stock_daily_preview_is_read_only_and_exposes_actual_v3_request():
    result = run_preview("stock_daily", "SSI", "2026-09-08", client=V3())
    assert result["request"]["params"] == {
        "symbol": "SSI",
        "from": "2026/09/08",
        "to": "2026/09/08",
        "pageIndex": 1,
        "pageSize": 1000,
    }
