from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class StreamType:
    name: str
    prefix: str
    target: str
    label: str
    expected_fields: tuple[str, ...]

QUOTE_FIELDS = (
    "RType","TradingDate","Time","TradingTime","ISIN","Symbol","Ceiling","Floor","RefPrice","Open","Close","High","Low","Avg","AvgPrice","PriorVal","LastPrice","Change","RatioChange","EstMatchedPrice","LastVol","TotalVal","TotalVol","MarketId","MarketID","Exchange","TradingSession","TradingStatus",
    *[f"BidPrice{i}" for i in range(1,11)], *[f"BidVol{i}" for i in range(1,11)], *[f"AskPrice{i}" for i in range(1,11)], *[f"AskVol{i}" for i in range(1,11)]
)
STREAM_TYPES: dict[str, StreamType] = {
    "securities-status": StreamType("securities-status", "F", "symbols", "Securities Status", ("RType","Rtype","MarketId","TradingDate","Time","Symbol","TradingSession","TradingStatus","Exchange")),
    "quote": StreamType("quote", "X-QUOTE", "symbols", "Market Data Quote", QUOTE_FIELDS),
    "trade": StreamType("trade", "X-TRADE", "symbols", "Market Data Trade", QUOTE_FIELDS),
    "foreign-room": StreamType("foreign-room", "R", "symbols", "Foreign Room Data", ("RType","TradingDate","Time","ISIN","Symbol","TotalRoom","CurrentRoom","FBuyVol","BuyVol","FSellVol","SellVol","FBuyVal","BuyVal","FSellVal","SellVal","MarketId","Exchange")),
    "index": StreamType("index", "MI", "index_codes", "Index Data", ("RType","IndexId","IndexID","IndexValEst","IndexValue","PriorIndexValue","TradingDate","Time","Change","RatioChange","TotalTrade","TotalQtty","TotalValue","IndexType","IndexName","Advances","NoChanges","Declines","Ceilings","Floors","TotalQttyPT","TotalValuePT","TotalQttyOD","TotalValueOD","AllQty","AllValue","TradingSession","Market","MarketId","Exchange")),
    "realtime-bar": StreamType("realtime-bar", "B", "symbols", "Realtime Bars", ("RType","Time","TradingTime","Symbol","Open","High","Low","Close","Volume","Value")),
}
RUN_ALL_ORDER = tuple(STREAM_TYPES)

def build_channels(kind: str, *, symbols: list[str] | None = None, index_codes: list[str] | None = None, exact_channel: str | None = None) -> list[str]:
    if exact_channel:
        return [exact_channel]
    st = STREAM_TYPES[kind]
    values = index_codes if st.target == "index_codes" else symbols
    values = values or []
    return [f"{st.prefix}:{str(v).upper()}" for v in values]
