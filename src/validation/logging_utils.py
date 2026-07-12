from __future__ import annotations

import logging
from typing import Any

from src.validation.models import ValidationResult

logger = logging.getLogger(__name__)


def log_validation_result(result: ValidationResult, dataset: str, context: dict) -> None:
    for severity, issues in (("error", result.errors), ("warning", result.warnings)):
        for issue in issues:
            parts: dict[str, Any] = {
                "dataset": dataset,
                **context,
                "code": issue.code,
                "field": issue.field,
                "actual": issue.actual_value,
                "expected": issue.expected_value,
            }
            msg = "Data validation %s %s" % (severity, " ".join(f"{k}={v}" for k, v in parts.items() if v is not None))
            if severity == "error":
                logger.error(msg)
            else:
                logger.warning(msg)
