"""Small adapter contract; adapters fetch/map but never persist."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AdapterResult:
    source: str
    dataset: str
    raw: list[dict[str, Any]]
    clean: list[dict[str, Any] | None]
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    mapping_report: dict[str, Any] = field(default_factory=dict)


class DataSourceAdapter(Protocol):
    source_id: str

    def fetch(self, dataset: str, identity: str, date: str, *, context: dict | None = None) -> AdapterResult: ...
