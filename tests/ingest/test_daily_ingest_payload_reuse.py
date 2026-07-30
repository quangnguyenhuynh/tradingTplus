import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

daily_mod = importlib.import_module("src.pipeline.daily")
foreign_mod = importlib.import_module("src.pipeline.foreign_trading")


def _daily(**overrides):
    base = {
        "Symbol": "SSI",
        "TradingDate": "18/06/2026",
        "RefPrice": "10.0",
        "CeilingPrice": "11.0",
        "FloorPrice": "9.0",
        "OpenPrice": "10.1",
        "HighestPrice": "10.8",
        "LowestPrice": "9.8",
        "ClosePrice": "10.5",
        "TotalMatchVol": "100",
        "TotalMatchVal": "1050",
        "TotalTradedVol": "100",
        "TotalTradedValue": "1050",
        "ForeignBuyVolTotal": "10",
        "ForeignSellVolTotal": "3",
        "ForeignBuyValTotal": "100",
        "ForeignSellValTotal": "30",
        "ForeignCurrentRoom": "1000",
    }
    base.update(overrides)
    return base


class _SSI:
    def __init__(self, payload):
        self.payload = payload
        self.daily_price_calls = 0
        self.foreign_calls = 0

    def get_daily_price(self, symbol, date):
        self.daily_price_calls += 1
        return self.payload

    def get_foreign_trading(self, symbol=None, date=None, market=None):
        self.foreign_calls += 1
        item = self.get_daily_price(symbol, date)
        return [item] if item else []


class _DB:
    def __init__(self):
        self.raw_daily_records = []
        self.stock_daily_records = []
        self.foreign_records = []

    def get_symbols(self):
        return ["SSI"]

    def upsert_raw_daily(self, records):
        self.raw_daily_records.extend(records)

    def upsert_stock_daily(self, records):
        self.stock_daily_records.extend(records)

    def upsert_foreign(self, records):
        self.foreign_records.extend(records)


def _patch_daily_dependencies(monkeypatch, ssi, db):
    monkeypatch.setattr(daily_mod, "SSIApi", lambda: ssi)
    monkeypatch.setattr(daily_mod, "SupabaseClient", lambda: db)


def test_daily_ingest_stores_foreign_fields_only_in_stock_daily(monkeypatch):
    payload = _daily()
    ssi = _SSI(payload)
    db = _DB()
    _patch_daily_dependencies(monkeypatch, ssi, db)

    summary = daily_mod.run_daily_ingest("18/06/2026")

    assert summary["status"] == "OK"
    assert ssi.daily_price_calls == 1
    assert ssi.foreign_calls == 0
    assert db.raw_daily_records[0]["payload"] is payload
    assert db.stock_daily_records[0]["raw"] is payload
    assert db.stock_daily_records[0]["foreign_buy_vol_total"] == 10
    assert db.stock_daily_records[0]["foreign_sell_vol_total"] == 3
    assert db.stock_daily_records[0]["foreign_buy_val_total"] == 100
    assert db.stock_daily_records[0]["foreign_sell_val_total"] == 30
    assert db.stock_daily_records[0]["foreign_current_room"] == 1000
    assert db.foreign_records == []
    assert summary["total_foreign"] == 0


def test_daily_ingest_missing_foreign_fields_does_not_refetch_or_create_foreign(monkeypatch):
    payload = _daily(
        ForeignBuyVolTotal=None,
        ForeignSellVolTotal=None,
        ForeignBuyValTotal=None,
        ForeignSellValTotal=None,
        ForeignCurrentRoom=None,
    )
    ssi = _SSI(payload)
    db = _DB()
    _patch_daily_dependencies(monkeypatch, ssi, db)

    summary = daily_mod.run_daily_ingest("18/06/2026")

    assert summary["status"] == "OK"
    assert ssi.daily_price_calls == 1
    assert ssi.foreign_calls == 0
    assert db.stock_daily_records
    assert db.stock_daily_records[0]["foreign_buy_vol_total"] is None
    assert db.stock_daily_records[0]["foreign_sell_vol_total"] is None
    assert db.stock_daily_records[0]["foreign_buy_val_total"] is None
    assert db.stock_daily_records[0]["foreign_sell_val_total"] is None
    assert db.stock_daily_records[0]["foreign_current_room"] is None
    assert db.foreign_records == []
    assert summary["total_foreign"] == 0


def test_daily_ingest_keeps_valid_ohlcv_when_price_context_is_zero(monkeypatch):
    payload = _daily(RefPrice=0, CeilingPrice="0", FloorPrice=0.0)
    ssi = _SSI(payload)
    db = _DB()
    _patch_daily_dependencies(monkeypatch, ssi, db)

    summary = daily_mod.run_daily_ingest("18/06/2026")

    assert summary["status"] == "OK"
    assert summary["error_count"] == 0
    assert db.raw_daily_records[0]["payload"] is payload
    assert payload["RefPrice"] == 0
    assert db.stock_daily_records[0]["ref_price"] is None
    assert db.stock_daily_records[0]["ceiling_price"] is None
    assert db.stock_daily_records[0]["floor_price"] is None


def test_daily_ingest_keeps_corporate_action_price_limit_warning(monkeypatch):
    payload = _daily(RefPrice="20", CeilingPrice="22", FloorPrice="18")
    ssi = _SSI(payload)
    db = _DB()
    _patch_daily_dependencies(monkeypatch, ssi, db)

    summary = daily_mod.run_daily_ingest("18/06/2026")

    assert summary["status"] == "OK"
    assert summary["error_count"] == 0
    assert db.stock_daily_records


def test_fetch_foreign_for_symbol_independent_call_still_fetches_daily_stock_price():
    payload = _daily(ForeignBuyVolTotal="", ForeignSellVolTotal="5")
    ssi = _SSI(payload)

    record = foreign_mod.fetch_foreign_for_symbol(ssi, "SSI", "18/06/2026")

    assert ssi.foreign_calls == 1
    assert ssi.daily_price_calls == 1
    assert record["foreign_buy_vol"] is None
    assert record["foreign_sell_vol"] == 5
    assert record["net_foreign_vol"] is None


def test_daily_ingest_wrong_payload_symbol_or_date_writes_no_stock_or_foreign(monkeypatch):
    ssi = _SSI(_daily(Symbol="HPG"))
    db = _DB()
    _patch_daily_dependencies(monkeypatch, ssi, db)

    summary = daily_mod.run_daily_ingest("18/06/2026")

    assert ssi.daily_price_calls == 1
    assert ssi.foreign_calls == 0
    assert summary["status"] == "FAILED"
    assert db.raw_daily_records
    assert db.stock_daily_records == []
    assert db.foreign_records == []


def test_daily_ingest_without_daily_stock_price_writes_nothing(monkeypatch):
    ssi = _SSI(None)
    db = _DB()
    _patch_daily_dependencies(monkeypatch, ssi, db)

    summary = daily_mod.run_daily_ingest("18/06/2026")

    assert ssi.daily_price_calls == 1
    assert ssi.foreign_calls == 0
    assert summary["status"] == "FAILED"
    assert db.raw_daily_records == []
    assert db.stock_daily_records == []
    assert db.foreign_records == []
