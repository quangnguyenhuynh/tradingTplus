import importlib

from src.database.client import SupabaseClient

init_symbols = importlib.import_module("src.pipeline.init_symbols")


def test_master_data_sync_keeps_all_master_endpoints(monkeypatch):
    calls = []

    class SSI:
        def get_symbols(self):
            calls.append(("Securities", None))
            return [{"Symbol": "SSI", "Market": "HOSE", "StockName": "SSI"}]

        def get_security_details(self, market=None):
            calls.append(("SecuritiesDetails", market))
            return []

        def get_index_list(self, exchange=None):
            calls.append(("IndexList", exchange))
            return [{"IndexCode": "VNINDEX", "Exchange": exchange}]

        def get_index_components(self, index_code):
            calls.append(("IndexComponents", index_code))
            return []

    class DB:
        def upsert_symbols(self, records):
            assert records

        def upsert_securities(self, records):
            assert records

        def upsert_indexes(self, records):
            assert records

        def upsert_index_components(self, records):
            raise AssertionError("empty components must not be written")

    monkeypatch.setattr(init_symbols, "SSIApi", SSI)
    monkeypatch.setattr(init_symbols, "SupabaseClient", DB)

    init_symbols.init_symbols()

    assert ("Securities", None) in calls
    assert [value for endpoint, value in calls if endpoint == "SecuritiesDetails"] == ["HOSE", "HNX", "UPCOM", "DER"]
    assert [value for endpoint, value in calls if endpoint == "IndexList"] == ["HOSE", "HNX", "UPCOM"]
    assert any(endpoint == "IndexComponents" for endpoint, _ in calls)


def test_master_upserts_preserve_existing_inactive_status(monkeypatch):
    db = object.__new__(SupabaseClient)
    writes = []
    monkeypatch.setattr(
        db,
        "_load_master_statuses",
        lambda table, key, keys: {"SSI": "inactive"} if table == "symbols" else {"VNINDEX": "inactive"},
    )
    monkeypatch.setattr(
        db,
        "_upsert_in_batches",
        lambda table, records, **kwargs: writes.append((table, records, kwargs)),
    )

    db.upsert_symbols([{"symbol": "SSI"}, {"symbol": "HPG"}])
    db.upsert_index_master([{"index_code": "VNINDEX"}, {"index_code": "VN30"}])

    assert writes[0][1] == [
        {"symbol": "SSI", "status": "inactive"},
        {"symbol": "HPG", "status": "active"},
    ]
    assert writes[1][1] == [
        {"index_code": "VNINDEX", "status": "inactive"},
        {"index_code": "VN30", "status": "active"},
    ]
