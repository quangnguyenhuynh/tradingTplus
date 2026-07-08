#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.orderbook_snapshot import build_orderbook_record
from src.ssi.streaming import SSIStreamingClient, normalize_quote

SAMPLE_QUOTE = {
    "DataType": "X",
    "Content": json.dumps({
        "RType": "X",
        "TradingDate": "08/07/2026",
        "Time": "09:15:01",
        "Symbol": "SSI",
        "Exchange": "HOSE",
        "TradingSession": "LO",
        "TradingStatus": "T",
        "LastPrice": 25000,
        "TotalVol": 123456,
        "TotalVal": 3000000000,
        "BidPrice1": 24950,
        "BidVol1": 1000,
        "AskPrice1": 25050,
        "AskVol1": 900,
        "BidPrice2": 24900,
        "BidVol2": 700,
        "AskPrice2": 25100,
        "AskVol2": 800,
    }),
}


def main() -> None:
    raw = json.dumps(SAMPLE_QUOTE)
    parsed = SSIStreamingClient.parse_message(raw)
    normalized = normalize_quote(parsed)
    record = build_orderbook_record("SSI", normalized)
    print(f"parsed data_type: {parsed.get('data_type')}")
    print(f"normalized symbol: {normalized.get('Symbol') if normalized else None}")
    print(f"bid_price_1: {record.get('bid_price_1') if record else None}")
    print(f"bid_vol_1: {record.get('bid_vol_1') if record else None}")
    print(f"ask_price_1: {record.get('ask_price_1') if record else None}")
    print(f"ask_vol_1: {record.get('ask_vol_1') if record else None}")
    print(f"orderbook_imbalance: {record.get('orderbook_imbalance') if record else None}")
    print(json.dumps(record, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
