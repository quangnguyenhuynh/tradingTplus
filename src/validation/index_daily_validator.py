"""Validation for normalized SSI DailyIndex rows."""
from __future__ import annotations

import math
from typing import Any

from src.validation.models import ValidationIssue, ValidationResult

NON_NEGATIVE = ("total_trade", "total_match_vol", "total_match_val", "total_deal_vol", "total_deal_val", "total_vol", "total_val", "advances", "no_changes", "declines", "ceilings", "floors")


def validate_index_daily_record(record: dict) -> ValidationResult:
    errors: list[ValidationIssue] = []; warnings: list[ValidationIssue] = []
    def issue(code: str, message: str, severity: str, field: str, actual: Any, expected: Any) -> None:
        target = errors if severity == "error" else warnings
        target.append(ValidationIssue(code, message, severity, field, actual, expected))
    for field in ("index_code", "trading_date"):
        if record.get(field) in (None, ""):
            issue("INDEX_REQUIRED_FIELD_MISSING", f"Required field {field} is missing", "error", field, record.get(field), "non-empty")
    for field in ("index_value", "change", "ratio_change", *NON_NEGATIVE):
        value = record.get(field)
        if value is None: continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            issue("INDEX_NON_FINITE_NUMERIC", f"{field} must be finite", "error", field, value, "finite number"); continue
        if field == "index_value" and value <= 0:
            issue("INDEX_NON_POSITIVE_VALUE", "index_value must be positive", "error", field, value, "> 0")
        if field in NON_NEGATIVE and value < 0:
            issue("INDEX_NEGATIVE_COUNT_OR_TOTAL", f"{field} must be non-negative", "error", field, value, ">= 0")
    for total, match, deal in (("total_vol", "total_match_vol", "total_deal_vol"), ("total_val", "total_match_val", "total_deal_val")):
        if all(record.get(key) is not None for key in (total, match, deal)):
            expected = record[match] + record[deal]
            tolerance = max(1e-6, abs(expected) * 1e-6)
            if abs(record[total] - expected) > tolerance:
                issue("INDEX_TOTAL_COMPONENT_MISMATCH", f"{total} differs from {match} + {deal}", "warning", total, record[total], expected)
    return ValidationResult(not errors, errors, warnings)
