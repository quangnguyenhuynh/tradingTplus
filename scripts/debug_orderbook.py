#!/usr/bin/env python3
"""Debug SSI orderbook responses without DB writes."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ssi.api import SSIApi
from src.pipeline.date_utils import latest_previous_weekday

SYMBOL = "SSI"
DATE = latest_previous_weekday().strftime("%d/%m/%Y")
ORDERBOOK_METHODS = (
    "get_orderbook",
    "get_order_book",
    "get_stock_orderbook",
    "get_bid_ask",
)


def _print_json(title: str, data: Any) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print('=' * 80)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _parse_args() -> tuple[str, str]:
    symbol = sys.argv[1] if len(sys.argv) >= 2 else SYMBOL
    date = sys.argv[2] if len(sys.argv) >= 3 else DATE
    return symbol, date


def _find_orderbook_method(ssi: SSIApi) -> Callable[..., Any] | None:
    for method_name in ORDERBOOK_METHODS:
        method = getattr(ssi, method_name, None)
        if callable(method):
            print(f"Using SSIApi.{method_name}()")
            return method

    return None


def _call_orderbook(method: Callable[..., Any], symbol: str, date: str) -> Any:
    try:
        return method(symbol, date)
    except TypeError:
        return method(symbol)


def _as_number(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_value(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _extract_levels_from_list(rows: list[Any]) -> list[dict[str, Any]]:
    levels = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue

        bid_price = _find_value(row, ("BidPrice", "bidPrice", "Bid", "bid"))
        bid_volume = _find_value(row, ("BidVolume", "bidVolume", "BidVol", "bidVol"))
        ask_price = _find_value(row, ("AskPrice", "askPrice", "Ask", "ask"))
        ask_volume = _find_value(row, ("AskVolume", "askVolume", "AskVol", "askVol"))

        values = (bid_price, bid_volume, ask_price, ask_volume)
        if any(value is not None for value in values):
            levels.append(
                {
                    "level": row.get("Level") or row.get("level") or index,
                    "bid_price": bid_price,
                    "bid_volume": bid_volume,
                    "ask_price": ask_price,
                    "ask_volume": ask_volume,
                }
            )

    return levels


def _extract_levels_from_dict(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("levels", "Levels", "orderbook", "OrderBook", "data", "dataList"):
        value = data.get(key)
        if isinstance(value, list):
            levels = _extract_levels_from_list(value)
            if levels:
                return levels

    levels = []
    for index in range(1, 11):
        bid_price = _find_value(
            data,
            (f"BidPrice{index}", f"Bid{index}", f"bidPrice{index}"),
        )
        bid_volume = _find_value(
            data,
            (f"BidVolume{index}", f"BidVol{index}", f"bidVolume{index}"),
        )
        ask_price = _find_value(
            data,
            (f"AskPrice{index}", f"Ask{index}", f"askPrice{index}"),
        )
        ask_volume = _find_value(
            data,
            (f"AskVolume{index}", f"AskVol{index}", f"askVolume{index}"),
        )

        values = (bid_price, bid_volume, ask_price, ask_volume)
        if any(value is not None for value in values):
            levels.append(
                {
                    "level": index,
                    "bid_price": bid_price,
                    "bid_volume": bid_volume,
                    "ask_price": ask_price,
                    "ask_volume": ask_volume,
                }
            )

    return levels


def _extract_levels(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return _extract_levels_from_list(data)

    if isinstance(data, dict):
        return _extract_levels_from_dict(data)

    return []


def _print_levels(levels: list[dict[str, Any]]) -> None:
    print("\nORDERBOOK TABLE")
    print("Level | BidPrice | BidVolume | AskPrice | AskVolume")
    print("-" * 80)

    total_bid_volume = 0.0
    total_ask_volume = 0.0
    has_bid_volume = False
    has_ask_volume = False

    for level in levels:
        bid_volume = _as_number(level["bid_volume"])
        ask_volume = _as_number(level["ask_volume"])
        if bid_volume is not None:
            total_bid_volume += bid_volume
            has_bid_volume = True
        if ask_volume is not None:
            total_ask_volume += ask_volume
            has_ask_volume = True

        print(
            f"{level['level']} | {level['bid_price']} | {level['bid_volume']} | "
            f"{level['ask_price']} | {level['ask_volume']}"
        )

    if has_bid_volume:
        print(f"\nTotal bid volume: {total_bid_volume:g}")
    if has_ask_volume:
        print(f"Total ask volume: {total_ask_volume:g}")


def main() -> None:
    symbol, date = _parse_args()
    ssi = SSIApi()
    method = _find_orderbook_method(ssi)

    if method is None:
        print("No existing orderbook method found in SSIApi.")
        print(f"Checked methods: {', '.join(ORDERBOOK_METHODS)}")
        return

    data = _call_orderbook(method, symbol, date)
    _print_json("ORDERBOOK full JSON", data)

    if not data:
        print("\nNo orderbook data returned by SSI API.")
        return

    levels = _extract_levels(data)
    if levels:
        _print_levels(levels)
    else:
        print("\nCannot parse orderbook structure automatically.")


if __name__ == "__main__":
    main()
