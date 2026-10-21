"""Deterministic, versioned EOD technical screening; no signal semantics."""
from __future__ import annotations

import math
from typing import Any

VERSION = "v1"
FIELDS = ("close", "ema20", "ema50", "rsi14", "macd_histogram", "volume_ratio", "value_ratio")
RULES = ("trend", "rsi", "macd", "volume", "value")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def evaluate(row: dict[str, Any] | None) -> dict[str, Any]:
    """Evaluate one completed daily feature row with explicit missing-data status.

    Score is only the fraction of five satisfied rules, NOT probability or return.
    """
    source = row or {}
    values = {field: _number(source.get(field)) for field in FIELDS}
    missing = [
        field for field, value in values.items()
        if value is None
        or (field in ("close", "ema20", "ema50") and value <= 0)
        or (field == "rsi14" and not 0 <= value <= 100)
        or (field in ("volume_ratio", "value_ratio") and value < 0)
    ]
    conditions: dict[str, bool | None] = {}
    depends = {
        "trend": ("close", "ema20", "ema50"),
        "rsi": ("rsi14",),
        "macd": ("macd_histogram",),
        "volume": ("volume_ratio",),
        "value": ("value_ratio",),
    }
    for rule, required in depends.items():
        if any(field in missing for field in required):
            conditions[rule] = None
        elif rule == "trend":
            conditions[rule] = values["close"] > values["ema20"] > values["ema50"]
        elif rule == "rsi":
            conditions[rule] = 50 <= values["rsi14"] <= 70
        elif rule == "macd":
            conditions[rule] = values["macd_histogram"] > 0
        else:
            conditions[rule] = values["volume_ratio" if rule == "volume" else "value_ratio"] >= 1

    status = (
        "NOT_EVALUABLE" if missing
        else "PASS" if all(conditions.values())
        else "FAIL"
    )
    score = None if missing else 20 * sum(bool(value) for value in conditions.values())
    return {
        "status": status,
        "score": score,
        "rule_results": {"conditions": conditions, "inputs": values},
        "missing_fields": missing,
    }
