"""Configurable binary-weighted V2; V1 in rules.py stays unchanged."""
from __future__ import annotations

from typing import Any

from .rules import _number


def evaluate_v2(source: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, Any]:
    row = source or {}
    values = {field: _number(row.get(field)) for field in config["required_inputs"]}
    invalid = [
        field for field, value in values.items()
        if value is None
        or (field in ("close", "ema20", "ema50") and value <= 0)
        or (field == "rsi14" and not 0 <= value <= 100)
        or (field in ("volume_ratio", "value_ratio") and value < 0)
    ]
    by_rule: dict[str, dict[str, Any]] = {}
    total = 0
    for spec in config["rules"]:
        rid, kind = spec["id"], spec["kind"]
        fields = {
            "trend": ("close", "ema20", "ema50"),
            "rsi": ("rsi14",),
            "macd": ("macd_histogram",),
            "volume": ("volume_ratio",),
            "value": ("value_ratio",),
        }[rid]
        if any(field in invalid for field in fields):
            passed = None
        elif kind == "ema_stack":
            passed = values["close"] > values["ema20"] > values["ema50"]
        elif kind == "range_inclusive":
            passed = spec["min"] <= values[spec["field"]] <= spec["max"]
        elif kind == "greater_than":
            passed = values[spec["field"]] > spec["threshold"]
        elif kind == "greater_or_equal":
            passed = values[spec["field"]] >= spec["threshold"]
        else:
            raise ValueError(f"Unsupported V2 rule kind {kind!r}")
        earned = None if passed is None else spec["weight"] if passed else 0
        if earned is not None:
            total += earned
        by_rule[rid] = {
            "passed": passed,
            "weight": spec["weight"],
            "earned": earned,
            "description_vi": spec["description_vi"],
            "description_en": spec["description_en"],
        }

    status = (
        "NOT_EVALUABLE" if invalid else
        "PASS" if total >= config["passing_score"] else "FAIL"
    )
    return {
        "status": status,
        "score": None if invalid else total,
        "rule_results": {
            "conditions": {key: detail["passed"] for key, detail in by_rule.items()},
            "inputs": values,
            "weighted_rules": by_rule,
            "passing_score": config["passing_score"],
            "scoring_method": config["scoring_method"],
        },
        "missing_fields": invalid,
    }
