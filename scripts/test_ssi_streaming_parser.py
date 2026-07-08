#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.orderbook_snapshot import build_orderbook_record
from src.ssi.streaming import normalize_quote, parse_message


def main() -> None:
    raw = {
        "DataType": "X",
        "Content": json.dumps({
            "RType": "X",
            "Symbol": "SSI",
            "TradingDate": "08/07/2026",
            "Time": "09:30:00",
            "Exchange": "HOSE",
            "LastPrice": 25000,
            "TotalVol": 10000,
            "TotalVal": 250000000,
            "BidPrice1": 24950,
            "BidVol1": 1000,
            "AskPrice1": 25050,
            "AskVol1": 900,
        }),
    }
    parsed = parse_message(raw)
    quote = normalize_quote(parsed)
    record = build_orderbook_record("SSI", quote.get("raw"))
    print("Parsed message:")
    print(json.dumps(parsed, indent=2, ensure_ascii=False, default=str))
    print("Normalized quote:")
    print(json.dumps(quote, indent=2, ensure_ascii=False, default=str))
    print("Mapped orderbook:")
    print(json.dumps(record, indent=2, ensure_ascii=False, default=str))
    assert quote["symbol"] == "SSI"
    assert quote["bid_price_1"] == 24950
    assert quote["bid_vol_1"] == 1000
    assert record["bid_price_1"] == 24950.0
    assert record["orderbook_imbalance"] is not None
    print("✅ offline parser test passed")


if __name__ == "__main__":
    main()
