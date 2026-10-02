from copy import deepcopy

import pytest

from src.data_sources.ssi_v3 import SSIV3Adapter
from src.pipeline.daily_service import fetch_daily_for_symbol_with_clients
from src.ssi.v3 import PageResult


SAMPLE = {
    "symbol": "SSI", "tradingDate": "2026/10/01", "priceChange": "50",
    "priceChangePercentage": "0.25", "open": "20150", "high": "20550",
    "low": "20100", "close": "20150", "average": "20245",
    "totalMatch": "21997400", "totalMatchValue": "445333630000",
    "totalBuy": "10449", "totalTradeBuy": "46258280", "totalSell": "13706",
    "totalTradeSell": "46747968", "totalForeignBuy": "2430312",
    "totalForeignBuyValue": "49137706200", "totalForeignSell": "2379769",
    "totalForeignSellValue": "48182860450", "remainForeignRoom": "2100488217",
    "totalForeignRoom": "3003293801", "totalDeal": "9343900",
    "totalDealValue": "194498820000", "openInterest": None, "settlementPrice": None,
}


class Client:
    def __init__(self, rows): self.rows = rows
    def securities_summary(self, symbol, date):
        return PageResult(self.rows, 1, [])


def test_v3_stock_daily_maps_verified_sample_and_preserves_original_raw():
    raw = deepcopy(SAMPLE)
    result = SSIV3Adapter(Client([raw])).fetch("stock_daily", "SSI", "01/10/2026")
    clean = result.clean[0]
    assert clean is not None
    assert (clean["symbol"], clean["trading_date"]) == ("SSI", "2026-10-01")
    assert [clean[key] for key in ("open_price", "highest_price", "lowest_price", "close_price", "average_price")] == [20150, 20550, 20100, 20150, 20245]
    assert clean["total_traded_vol"] == 31341300
    assert clean["total_traded_value"] == 639832450000
    assert clean["net_foreign_vol"] == 50543
    assert clean["net_foreign_val"] == 954845750
    assert clean["foreign_total_room"] == 3003293801
    assert [clean[key] for key in ("ceiling_price", "floor_price", "ref_price", "close_price_adjusted")] == [None] * 4
    assert clean["raw"] is raw and clean["raw"] == SAMPLE
    assert "summary.symbol" not in clean["raw"]


@pytest.mark.parametrize("change", [{"symbol": "HPG"}, {"tradingDate": "2026/09/30"}])
def test_v3_stock_daily_rejects_clean_outside_request_scope_but_retains_raw(change):
    raw = {**SAMPLE, **change}
    result = SSIV3Adapter(Client([raw])).fetch("stock_daily", "SSI", "01/10/2026")
    assert result.raw == [raw]
    assert result.clean == [None]
    assert {error["code"] for error in result.validation_errors} == {"REQUEST_SCOPE_MISMATCH"}


def test_v3_stock_daily_derived_values_strictly_propagate_null_and_preserve_zero():
    raw = {**SAMPLE, "totalMatch": None, "totalDeal": "100", "totalForeignBuy": "0", "totalForeignSell": "100"}
    clean = SSIV3Adapter(Client([raw])).fetch("stock_daily", "SSI", "01/10/2026").clean[0]
    assert clean["total_traded_vol"] is None
    assert clean["net_foreign_vol"] == -100


def test_v3_daily_service_persists_source_and_unchanged_payload():
    class DB:
        def __init__(self): self.raw, self.clean = [], []
        def upsert_raw_daily(self, records): self.raw.extend(records)
        def upsert_stock_daily(self, records): self.clean.extend(records)

    raw, db = deepcopy(SAMPLE), DB()
    summary = fetch_daily_for_symbol_with_clients(
        SSIV3Adapter(Client([raw])), db, "SSI", "01/10/2026"
    )
    assert summary["status"] == "OK"
    assert db.raw[0]["source"] == "ssi_v3"
    assert db.raw[0]["payload"] is raw
    assert db.clean[0]["raw"] is raw
