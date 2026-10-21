"""Database-backed scope resolution for SSI index codes."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def normalize_index_scope(indexes: Iterable[Any] | None) -> list[str] | None:
    if indexes is None:
        return None
    values: list[str] = []
    seen: set[str] = set()
    for value in indexes:
        text = str(value).strip() if value is not None else ""
        key = text.casefold()
        if text and key not in seen:
            seen.add(key); values.append(text)
    if not values:
        raise ValueError("Explicit index scope must contain at least one non-blank index code")
    return values


def _load_master(db: Any, *, active_only: bool) -> list[str]:
    def _query():
        query = db.client.table("index_master").select("index_code")
        if active_only:
            query = query.eq("status", "active")
        return query.order("index_code").execute()

    scope = "active index_master scope" if active_only else "index_master scope"
    result = db._with_retry(_query, action_name=f"load {scope}")
    return [str(row["index_code"]) for row in (result.data or []) if row.get("index_code")]


def resolve_index_scope(db: Any, indexes: Iterable[Any] | None) -> tuple[list[str], list[str] | None]:
    requested = normalize_index_scope(indexes)
    master = _load_master(db, active_only=requested is None)
    if not master:
        detail = " has no active rows" if requested is None else " is empty"
        raise ValueError(f"index_master{detail}; run `python main.py sync-master-data` or update master status")
    canonical = {code.casefold(): code for code in master}
    if requested is None:
        return master, None
    unknown = [code for code in requested if code.casefold() not in canonical]
    if unknown:
        raise ValueError(f"Unknown index code(s) in index_master: {', '.join(unknown)}")
    return [canonical[code.casefold()] for code in requested], requested


def index_scope_summary(resolved: list[str], requested: list[str] | None) -> dict[str, Any]:
    return {"index_scope": "EXPLICIT" if requested is not None else "ALL_MASTER", "requested_indexes": requested, "indexes": resolved, "index_count": len(resolved)}
