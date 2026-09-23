"""Pure, Decimal-based foreign EOD rolling feature calculation."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from .validator import decimal_value, validate_source_row

FORMULA_VERSION = 2
WINDOW_SIZES = (5, 20)
MAX_SOURCE_ROWS = 20
FINGERPRINT_FIELDS = (
    "symbol",
    "trading_date",
    "foreign_buy_vol_total",
    "foreign_sell_vol_total",
    "net_foreign_vol",
    "foreign_buy_val_total",
    "foreign_sell_val_total",
    "net_foreign_val",
    "total_traded_value",
)


def _fingerprint(symbol: str, target: str, rows: list[dict]) -> str:
    values = [
        [None if row.get(field) is None else str(row.get(field)) for field in FINGERPRINT_FIELDS]
        for row in rows
    ]
    body = {
        "formula_version": FORMULA_VERSION,
        "symbol": symbol,
        "target": target,
        "window_basis": "symbol_rows",
        "rows": values,
    }
    return hashlib.sha256(
        json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _window(rows: list[dict], size: int) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = rows[-size:]
    quality: dict[str, Any] = {
        "status": "VALID",
        "required_rows": size,
        "observed_rows": len(selected),
        "start": str(selected[0]["trading_date"]) if selected else None,
        "end": str(selected[-1]["trading_date"]) if selected else None,
        "dates": [str(row["trading_date"]) for row in selected],
        "reasons": [],
    }
    if len(selected) < size:
        quality.update(status="INSUFFICIENT_HISTORY", reasons=["INSUFFICIENT_HISTORY"])
        return {}, quality

    invalid = sorted({reason for row in selected for reason in validate_source_row(row)})
    value_invalid = [reason for reason in invalid if "VOLUME" not in reason and "_VOL_" not in reason]
    if value_invalid:
        quality.update(status="INVALID_SOURCE", reasons=invalid)
    elif invalid:
        quality.update(status="PARTIAL", reasons=invalid)

    def vals(field: str) -> list[Decimal | None]:
        values: list[Decimal | None] = []
        for row in selected:
            try:
                values.append(decimal_value(row.get(field)))
            except ValueError:
                values.append(None)
        return values

    buy, sell, net, turnover = (
        vals(field)
        for field in (
            "foreign_buy_val_total",
            "foreign_sell_val_total",
            "net_foreign_val",
            "total_traded_value",
        )
    )
    out: dict[str, Any] = {}
    suffix = f"_{size}d"
    net_invalid = any(
        reason.startswith("INVALID_NET_FOREIGN_VAL")
        or reason == "NET_VALUE_MISMATCH"
        for reason in invalid
    )
    if all(value is not None for value in net) and not net_invalid:
        valid_net = [value for value in net if value is not None]
        out["net_value" + suffix] = sum(valid_net, Decimal(0))
        out["buy_days" + suffix] = sum(value > 0 for value in valid_net)
        out["sell_days" + suffix] = sum(value < 0 for value in valid_net)
    if all(value is not None for value in buy + sell) and not any(
        reason.startswith("INVALID_FOREIGN_BUY_VAL_TOTAL")
        or reason.startswith("INVALID_FOREIGN_SELL_VAL_TOTAL")
        or reason.startswith("NEGATIVE_FOREIGN_BUY_VAL_TOTAL")
        or reason.startswith("NEGATIVE_FOREIGN_SELL_VAL_TOTAL")
        for reason in invalid
    ):
        out["activity_value" + suffix] = sum(
            [value for value in buy + sell if value is not None], Decimal(0)
        )

    denominator_ok = all(value is not None and value >= 0 for value in turnover)
    denominator = (
        sum([value for value in turnover if value is not None], Decimal(0))
        if denominator_ok
        else Decimal(0)
    )
    if denominator > 0 and "net_value" + suffix in out:
        out["net_value_ratio" + suffix] = out["net_value" + suffix] / denominator
    if denominator > 0 and "activity_value" + suffix in out:
        out["activity_ratio" + suffix] = out["activity_value" + suffix] / (Decimal(2) * denominator)
    if not denominator_ok or denominator == 0:
        quality["reasons"].append("DENOMINATOR_INVALID" if not denominator_ok else "DENOMINATOR_ZERO")
    quality["reasons"] = sorted(set(quality["reasons"]))
    if quality["reasons"] and quality["status"] == "VALID":
        quality["status"] = "PARTIAL"
    return out, quality


def calculate_symbol(rows: list[dict], target: str) -> dict[str, Any] | None:
    """Calculate V2 from the last rows of one symbol ending exactly at target."""
    eligible = [row for row in rows if str(row.get("trading_date")) <= target]
    if not eligible:
        return None
    symbols = {str(row.get("symbol", "")).upper() for row in eligible}
    if len(symbols) != 1:
        raise ValueError("MIXED_SYMBOL_SOURCE: calculator accepts one symbol")
    keys = [(next(iter(symbols)), str(row.get("trading_date"))) for row in eligible]
    if len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_SOURCE: duplicate symbol/trading_date rows")
    ordered = sorted(eligible, key=lambda row: str(row["trading_date"]))
    if str(ordered[-1]["trading_date"]) != target:
        return None

    used = ordered[-MAX_SOURCE_ROWS:]
    symbol = next(iter(symbols))
    result: dict[str, Any] = {
        "symbol": symbol,
        "trading_date": target,
        "formula_version": FORMULA_VERSION,
    }
    quality: dict[str, Any] = {"window_basis": "symbol_rows"}
    for size in WINDOW_SIZES:
        metrics, window_quality = _window(ordered, size)
        result.update(metrics)
        quality[str(size)] = window_quality

    current_metrics, current_quality = _window(ordered, 5)
    previous_metrics, previous_quality = _window(ordered[:-5], 5) if len(ordered) >= 5 else ({}, {
        "status": "INSUFFICIENT_HISTORY", "required_rows": 5, "observed_rows": 0,
        "start": None, "end": None, "dates": [], "reasons": ["INSUFFICIENT_HISTORY"],
    })
    for metric in ("net_value_ratio_5d", "activity_ratio_5d"):
        if metric in current_metrics and metric in previous_metrics:
            result[metric.replace("_5d", "_change_5d")] = current_metrics[metric] - previous_metrics[metric]
    quality["change_5d"] = {
        "status": "VALID" if all(
            key in result for key in ("net_value_ratio_change_5d", "activity_ratio_change_5d")
        ) else ("INSUFFICIENT_HISTORY" if len(ordered) < 10 else "PARTIAL"),
        "current": current_quality,
        "previous": previous_quality,
    }
    result["quality_status"] = quality
    result["source_window_start"] = str(used[0]["trading_date"])
    result["source_fingerprint"] = _fingerprint(symbol, target, used)
    return result
