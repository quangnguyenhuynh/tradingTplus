from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str  # "error" or "warning"
    field: str | None = None
    actual_value: Any = None
    expected_value: Any = None


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
