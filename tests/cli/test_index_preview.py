import json

import main
from src.database.client import SupabaseClient
from src.pipeline import index_daily_preview


PAYLOAD = {
    "IndexId": "VNINDEX",
    "TradingDate": "24/08/2026",
    "IndexValue": 1_245.5,
    "Change": None,
    "RatioChange": 0.25,
    "TotalVol": 123_456,
    "TotalVal": None,
}


class FakeSSI:
    def __init__(self, rows=None):
        self.rows = [PAYLOAD] if rows is None else rows
        self.calls = []

    def get_daily_index_items(self, index_code, date):
        self.calls.append((index_code, date))
        return self.rows


def _install_ssi(monkeypatch, fake):
    monkeypatch.setattr(index_daily_preview, "SSIApi", lambda: fake)


def test_preview_one_date_prints_normalized_table_without_db_writes(monkeypatch, capsys):
    fake = FakeSSI()
    _install_ssi(monkeypatch, fake)
    def fail_db_call(*args, **kwargs):
        raise AssertionError("database access called")

    monkeypatch.setattr(SupabaseClient, "__init__", fail_db_call)
    monkeypatch.setattr(SupabaseClient, "upsert_index_raw_daily", fail_db_call)
    monkeypatch.setattr(SupabaseClient, "upsert_index_daily", fail_db_call)

    assert main.main(["index-preview", "--date", "2026-08-24", "--indexes", "VNINDEX"]) == 0

    output = capsys.readouterr().out
    assert "VNINDEX | 2026-08-24 | 1245.5" in output
    assert "SSI_DailyIndex | OK" in output
    assert fake.calls == [("VNINDEX", "24/08/2026")]


def test_preview_accepts_documented_slash_date(monkeypatch, capsys):
    fake = FakeSSI()
    _install_ssi(monkeypatch, fake)
    assert main.main(["index-preview", "--date", "24/08/2026", "--indexes", "VNINDEX"]) == 0
    assert fake.calls == [("VNINDEX", "24/08/2026")]
    assert "VNINDEX | 2026-08-24" in capsys.readouterr().out


def test_preview_rejects_undocumented_date_separator(monkeypatch, capsys):
    _install_ssi(monkeypatch, FakeSSI())
    assert main.main(["index-preview", "--date", "24-08-2026", "--indexes", "VNINDEX"]) == 2
    assert "YYYY-MM-DD or DD/MM/YYYY" in capsys.readouterr().err


def test_preview_empty_response_prints_clear_message(monkeypatch, capsys):
    _install_ssi(monkeypatch, FakeSSI([]))

    assert main.main(["index-preview", "--date", "2026-08-24", "--indexes", "VNINDEX"]) == 0

    assert "No SSI index daily data returned for VNINDEX on 2026-08-24" in capsys.readouterr().out


def test_preview_raw_prints_raw_payload_json(monkeypatch, capsys):
    _install_ssi(monkeypatch, FakeSSI())

    assert main.main(["index-preview", "--date", "2026-08-24", "--indexes", "VNINDEX", "--raw"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output[0]["raw"] == [PAYLOAD]
    assert output[0]["source"] == "SSI_DailyIndex"
    assert output[0]["mapping_summary"] == [{
        "raw_field_count": len(PAYLOAD),
        "normalized_field_count": 22,
        "omitted_from_clean": [],
    }]


def test_preview_json_prints_valid_normalized_json(monkeypatch, capsys):
    _install_ssi(monkeypatch, FakeSSI())

    assert main.main(["index-preview", "--date", "2026-08-24", "--indexes", "VNINDEX", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output[0]["index_code"] == "VNINDEX"
    assert output[0]["change"] is None
    assert output[0]["total_val"] is None
    assert set(output[0]) == {
        "index_code", "trading_date", "index_value", "change", "ratio_change",
        "total_trade", "total_match_vol", "total_match_val", "total_deal_vol",
        "total_deal_val", "total_vol", "total_val", "advances", "no_changes",
        "declines", "ceilings", "floors", "type_index", "index_name",
        "trading_session", "market", "exchange",
    }


def test_preview_reports_raw_only_time_without_removing_it(monkeypatch, capsys):
    payload = {**PAYLOAD, "Time": "", "FutureSSIField": "kept"}
    _install_ssi(monkeypatch, FakeSSI([payload]))

    assert main.main(["index-preview", "--date", "2026-08-24", "--indexes", "VNINDEX", "--raw"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output[0]["raw"] == [payload]
    assert output[0]["mapping_summary"][0]["omitted_from_clean"] == ["Time", "FutureSSIField"]


def test_preview_range_fetches_each_inclusive_date(monkeypatch, capsys):
    fake = FakeSSI([])
    _install_ssi(monkeypatch, fake)

    assert main.main([
        "index-preview", "--from", "2026-08-23", "--to", "2026-08-24",
        "--indexes", "VNINDEX,HNXINDEX",
    ]) == 0

    assert fake.calls == [
        ("VNINDEX", "23/08/2026"), ("HNXINDEX", "23/08/2026"),
        ("VNINDEX", "24/08/2026"), ("HNXINDEX", "24/08/2026"),
    ]
    assert capsys.readouterr().out.count("No SSI index daily data returned") == 4
