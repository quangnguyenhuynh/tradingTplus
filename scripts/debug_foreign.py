#!/usr/bin/env python3
"""Debug SSI foreign trading responses without DB writes."""

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
FOREIGN_METHODS = (
    "get_foreign_trading",
    "get_foreign",
    "get_foreign_data",
    "get_stock_foreign",
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


def _find_foreign_method(ssi: SSIApi) -> Callable[..., Any] | None:
    for method_name in FOREIGN_METHODS:
        method = getattr(ssi, method_name, None)
        if callable(method):
            print(f"Using SSIApi.{method_name}()")
            return method

    return None


def _call_foreign(method: Callable[..., Any], symbol: str, date: str) -> Any:
    try:
        return method(symbol, date)
    except TypeError:
        return method(symbol)


def _find_value(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _as_number(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _net_value(buy_value: Any, sell_value: Any) -> Any:
    buy_number = _as_number(buy_value)
    sell_number = _as_number(sell_value)
    if buy_number is None or sell_number is None:
        return None

    return buy_number - sell_number


def _row_symbol(row: dict[str, Any]) -> Any:
    return _find_value(row, ("Symbol", "symbol", "Ticker", "ticker"))


def _extract_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]

    if isinstance(data, dict):
        for key in ("data", "dataList", "items", "rows", "foreignTrading"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]

        return [data]

    return []


def _filter_symbol(rows: list[dict[str, Any]], symbol: str) -> list[dict[str, Any]]:
    matching_rows = [
        row for row in rows
        if str(_row_symbol(row) or "").upper() == symbol.upper()
    ]
    return matching_rows or rows


def _to_foreign_record(
    row: dict[str, Any],
    default_symbol: str,
) -> dict[str, Any] | None:
    symbol = _row_symbol(row) or default_symbol
    buy_volume = _find_value(
        row,
        ("BuyVolume", "buyVolume", "ForeignBuyVolume", "buy_vol"),
    )
    sell_volume = _find_value(
        row,
        ("SellVolume", "sellVolume", "ForeignSellVolume", "sell_vol"),
    )
    buy_value = _find_value(
        row,
        ("BuyValue", "buyValue", "ForeignBuyValue", "buy_value"),
    )
    sell_value = _find_value(
        row,
        ("SellValue", "sellValue", "ForeignSellValue", "sell_value"),
    )
    net_volume = _find_value(row, ("NetVolume", "netVolume", "NetVol", "net_vol"))
    net_value = _find_value(row, ("NetValue", "netValue", "net_value"))

    if net_volume is None:
        net_volume = _net_value(buy_volume, sell_volume)
    if net_value is None:
        net_value = _net_value(buy_value, sell_value)

    values = (buy_volume, sell_volume, net_volume, buy_value, sell_value, net_value)
    if all(value is None for value in values):
        return None

    return {
        "symbol": symbol,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "net_volume": net_volume,
        "buy_value": buy_value,
        "sell_value": sell_value,
        "net_value": net_value,
    }


def _print_foreign_table(records: list[dict[str, Any]]) -> None:
    print("\nFOREIGN TRADING TABLE")
    print(
        "Symbol | BuyVolume | SellVolume | NetVolume | "
        "BuyValue | SellValue | NetValue"
    )
    print("-" * 100)

    for record in records:
        print(
            f"{record['symbol']} | "
            f"{record['buy_volume']} | "
            f"{record['sell_volume']} | "
            f"{record['net_volume']} | "
            f"{record['buy_value']} | "
            f"{record['sell_value']} | "
            f"{record['net_value']}"
        )


def main() -> None:
    symbol, date = _parse_args()
    ssi = SSIApi()
    method = _find_foreign_method(ssi)

    if method is None:
        print("No existing foreign trading method found in SSIApi.")
        print(f"Checked methods: {', '.join(FOREIGN_METHODS)}")
        return

    data = _call_foreign(method, symbol, date)
    _print_json("FOREIGN TRADING full JSON", data)

    if not data:
        print("\nNo foreign trading data returned by SSI API.")
        return

    rows = _filter_symbol(_extract_rows(data), symbol)
    records = [
        record for record in (_to_foreign_record(row, symbol) for row in rows)
        if record is not None
    ]

    if records:
        _print_foreign_table(records)
    else:
        print("\nCannot parse foreign trading structure automatically.")


if __name__ == "__main__":
    main()
