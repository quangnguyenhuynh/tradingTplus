"""Shared stock-symbol scope normalization for source-data pipelines."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def normalize_symbol_scope(symbols: Iterable[Any] | None) -> list[str] | None:
    """Normalize an explicit scope while preserving ``None`` as all-master scope."""
    if symbols is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for value in symbols:
        if value is None:
            continue
        symbol = str(value).strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            normalized.append(symbol)
    if not normalized:
        raise ValueError("Explicit symbol scope must contain at least one non-blank symbol")
    return normalized


def resolve_symbol_scope(db: Any, symbols: Iterable[Any] | None) -> tuple[list[str], list[str] | None]:
    """Return actual symbols and the normalized explicit request, if supplied."""
    requested = normalize_symbol_scope(symbols)
    if requested is not None:
        return requested, requested
    master_values = db.get_symbols()
    if not master_values:
        return [], None
    master_symbols = normalize_symbol_scope(master_values)
    return master_symbols or [], None


def symbol_scope_summary(resolved: list[str], requested: list[str] | None) -> dict[str, Any]:
    return {
        "symbol_scope": "EXPLICIT" if requested is not None else "ALL_ACTIVE",
        "requested_symbols": requested,
        "symbols": resolved,
        "symbol_count": len(resolved),
    }


__all__ = ["normalize_symbol_scope", "resolve_symbol_scope", "symbol_scope_summary"]
