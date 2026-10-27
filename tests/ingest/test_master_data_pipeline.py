import importlib

from src.database.client import SupabaseClient

init_symbols = importlib.import_module("src.ingest.master.init_symbols")




def test_master_upserts_preserve_existing_inactive_status(monkeypatch):
    db = object.__new__(SupabaseClient)
    writes = []
    monkeypatch.setattr(
        db,
        "_load_master_statuses",
        lambda table, key, keys, columns=("status",): ({"SSI": {"status": "inactive", "intraday_status": "active"}} if table == "symbols" else {"VNINDEX": {"status": "inactive"}}),
    )
    monkeypatch.setattr(
        db,
        "_upsert_in_batches",
        lambda table, records, **kwargs: writes.append((table, records, kwargs)),
    )

    db.upsert_symbols([{"symbol": "SSI"}, {"symbol": "HPG"}])
    db.upsert_index_master([{"index_code": "VNINDEX"}, {"index_code": "VN30"}])

    assert writes[0][1] == [
        {"symbol": "SSI", "status": "inactive", "intraday_status": "active"},
        {"symbol": "HPG", "status": "active", "intraday_status": "inactive"},
    ]
    assert writes[1][1] == [
        {"index_code": "VNINDEX", "status": "inactive"},
        {"index_code": "VN30", "status": "active"},
    ]


def test_master_sync_blocked_without_any_database_access(monkeypatch):
    monkeypatch.setattr(SupabaseClient, "__init__", lambda *_: (_ for _ in ()).throw(AssertionError("DB access")))
    result = init_symbols.init_symbols(dataset="index_master")
    assert result["status"] == "BLOCKED"
    assert len(result["datasets"]) == 1
