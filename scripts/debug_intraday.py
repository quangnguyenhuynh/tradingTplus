#!/usr/bin/env python3
"""Debug SSI daily price and intraday OHLC responses without DB writes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ssi.api import SSIApi
from src.intraday_value import calculate_trade_value

SYMBOL = "SSI"
DATE = "18/06/2026"


def _print_json(title: str, data: Any) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print('=' * 80)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _get_number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_non_decreasing(rows: list[dict[str, Any]], key: str) -> bool:
    values = [_get_number(row, key) for row in rows]
    numeric_values = [value for value in values if value is not None]

    if len(numeric_values) < 2:
        return False

    return all(
        current >= previous
        for previous, current in zip(numeric_values, numeric_values[1:])
    )


def _print_candle_table(candles: list[dict[str, Any]]) -> None:
    print("\nNORMALIZED INTRADAY SAMPLE")
    print("Time | Open | High | Low | Close | Volume | Calculated value | type(value) | Raw SSI Value")
    print("-" * 110)

    for candle in candles:
        value = calculate_trade_value(candle.get('Close'), candle.get('Volume'))
        print(
            f"{candle.get('Time', '')} | "
            f"{candle.get('Open', '')} | "
            f"{candle.get('High', '')} | "
            f"{candle.get('Low', '')} | "
            f"{candle.get('Close', '')} | "
            f"{candle.get('Volume', '')} | "
            f"{value} | "
            f"{type(value).__name__} | "
            f"{candle.get('Value', '')}"
        )


def _parse_args() -> tuple[str, str]:
    symbol = sys.argv[1] if len(sys.argv) >= 2 else SYMBOL
    date = sys.argv[2] if len(sys.argv) >= 3 else DATE
    return symbol, date


def main() -> None:
    symbol, date = _parse_args()
    ssi = SSIApi()

    daily = ssi.get_daily_price(symbol, date)
    _print_json("DAILY full JSON", daily)

    candles = ssi.get_intraday(symbol, date)
    if not candles:
        print("\nNo intraday candles returned by SSI API.")
        return

    print(f"\nTổng số candle intraday: {len(candles)}")
    _print_json("5 candle đầu", candles[:5])
    _print_json("5 candle cuối", candles[-5:])
    _print_candle_table(candles)

    volume_cumulative = _is_non_decreasing(candles, "Volume")

    print("\nVOLUME CHECK")
    volume_status = "cumulative" if volume_cumulative else "per-candle or reset/error"
    print(f"Volume: {volume_status}")
    print("Calculated value uses close * volume via calculate_trade_value(); raw SSI Value is informational only.")


if __name__ == "__main__":
    main()
