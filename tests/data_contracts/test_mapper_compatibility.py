"""Confirmed SSI v2 fixture shapes plus synthetic rejection coverage."""
from src.pipeline.daily_mapper import build_stock_daily_record, map_stock_daily_record
from src.pipeline.index_daily_mapper import build_index_daily_record
from src.pipeline.intraday_mapper import build_intraday_records
from src.pipeline.daily_service import fetch_daily_for_symbol_with_clients


def test_stock_daily_all_supported_fields_and_foreign_totals():
    fields={"PriceChange":-1,"PerPriceChange":-2,"CeilingPrice":12,"FloorPrice":8,"RefPrice":10,"OpenPrice":10,"HighestPrice":11,"LowestPrice":9,"ClosePrice":9.8,"AveragePrice":10.1,"ClosePriceAdjusted":9.7,"TotalMatchVol":1,"TotalMatchVal":2,"TotalDealVol":3,"TotalDealVal":4,"TotalTradedVol":5,"TotalTradedValue":6,"ForeignBuyVolTotal":7,"ForeignSellVolTotal":8,"ForeignBuyValTotal":9,"ForeignSellValTotal":10,"ForeignCurrentRoom":11,"Netforeivol":-1,"Netforeignval":-2,"TotalBuyTrade":12,"TotalBuyTradeVol":13,"TotalSellTrade":14,"TotalSellTradeVol":15}
    payload={"Symbol":"SSI","TradingDate":"18/06/2026",**fields}; clean=build_stock_daily_record("SSI","18/06/2026",payload)
    assert clean and clean["foreign_buy_vol_total"] == 7 and clean["total_traded_value"] == 6 and clean["raw"] is payload
    assert len(clean) == 31

def test_intraday_wrapper_keeps_1m_utc_value_and_raw_payload():
    candle={"Time":"09:15:00","Open":"10","High":11,"Low":9,"Close":"10.5","Volume":"100","Ignored":"raw-only"}
    raw,clean=build_intraday_records("SSI","18/06/2026",{"RefPrice":10},[candle])
    assert raw[0]["payload"] is candle and clean == [{"symbol":"SSI","time":"2026-06-18T02:15:00Z","open":10.0,"high":11.0,"low":9.0,"close":10.5,"volume":100,"timeframe":"1m","value":1050,"reference_price":10.0,"ceiling_price":None,"floor_price":None}]

def test_index_mapper_keeps_complete_clean_contract():
    payload={"IndexId":"VNINDEX","TradingDate":"25/08/2026","IndexValue":"1280.5","TotalMatchVol":10,"TotalDealVol":2,"TotalVol":12,"Nochanges":3,"Ceiling":4,"Floor":5}
    clean=build_index_daily_record("VNINDEX","25/08/2026",payload)
    assert clean and len(clean)==22 and clean["index_value"]==1280.5 and clean["no_changes"]==3

def test_mapping_error_blocks_clean_database_write_but_preserves_raw():
    calls=[]
    class SSI:
        def get_daily_price(self,symbol,date): return {"Symbol":symbol,"TradingDate":date,"OpenPrice":True}
    class DB:
        def upsert_raw_daily(self,rows): calls.append("raw")
        def upsert_stock_daily(self,rows): calls.append("clean")
    summary=fetch_daily_for_symbol_with_clients(SSI(),DB(),"SSI","18/06/2026")
    assert calls == ["raw"] and summary["daily_rows"] == 0
    assert summary["mapping_report"]["transform_errors"]
