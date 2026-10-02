"""Shared, side-effect-free canonical derived-field calculations."""
from __future__ import annotations

from typing import Any


STOCK_DAILY_DERIVATIONS = {
    "total_traded_vol": ("total_match_vol", "total_deal_vol", "add"),
    "total_traded_value": ("total_match_val", "total_deal_val", "add"),
    "net_foreign_vol": ("foreign_buy_vol_total", "foreign_sell_vol_total", "subtract"),
    "net_foreign_val": ("foreign_buy_val_total", "foreign_sell_val_total", "subtract"),
}


def apply_derived_fields(dataset: str, candidate: dict[str, Any]) -> dict[str, Any]:
    """Populate canonical derivations in place with strict NULL propagation."""
    if dataset != "stock_daily":
        return candidate
    for target, (left_field, right_field, operation) in STOCK_DAILY_DERIVATIONS.items():
        left, right = candidate.get(left_field), candidate.get(right_field)
        if left is None or right is None:
            candidate[target] = None
        elif operation == "add":
            candidate[target] = left + right
        else:
            candidate[target] = left - right
    return candidate
