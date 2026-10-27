"""Version-neutral master DTO boundary. No SSI response field assumptions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

MASTER_DATASETS = ("symbols", "securities", "index_master", "index_components")


@dataclass(frozen=True)
class MasterSnapshot:
    """Adapter must validate the entire source and prove its requested scope."""

    dataset: str
    records: list[dict[str, Any]]
    source_records: int
    complete: bool
    resolved_scope: dict[str, Any]
    mapping_version: str
    pagination: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    unsupported_fields: tuple[str, ...] = ()
    excluded_records: list[dict[str, Any]] = field(default_factory=list)
    # Optional version-neutral comparison guard for full-universe snapshots.
    retention_policy: dict[str, str] = field(default_factory=dict)


class MasterProvider(Protocol):
    def fetch(self, dataset: str) -> MasterSnapshot: ...


@dataclass(frozen=True)
class MasterCapability:
    source: str
    dataset: str
    order: int
    status: str  # READY, PREVIEW, BLOCKED, UNSUPPORTED
    verified: bool
    factory: Callable[[], MasterProvider]
    evidence: str
    note: str = ""


class MasterSourceError(RuntimeError):
    """Safe error code only; never include source bodies or credentials."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
