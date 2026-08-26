"""Explicit daily, backfill, and read-only preview orchestration."""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_index_date
from src.pipeline.index_scope import index_scope_summary, resolve_index_scope

from .calculator import compute_index_daily_features
from .repository import fetch_index_daily_context, frame_to_records, upsert_index_features


def _run(start_value: str, end_value: str, indexes, *, db=None, write: bool) -> dict[str, Any]:
    start = parse_index_date(start_value).iso
    end = parse_index_date(end_value).iso
    if start > end:
        raise ValueError("--from must be on or before --to")
    db = db or SupabaseClient()
    resolved, requested = resolve_index_scope(db, indexes)
    output: list[dict] = []
    source_counts: dict[str, int] = {}
    for code in resolved:
        rows = fetch_index_daily_context(db, code, start, end)
        requested_rows = [row for row in rows if start <= str(row["trading_date"]) <= end]
        source_counts[code] = len(requested_rows)
        if not requested_rows:
            continue
        calculated = compute_index_daily_features(pd.DataFrame(rows))
        mask = calculated["trading_date"].dt.date.astype(str).between(start, end)
        records = frame_to_records(calculated.loc[mask])
        if write:
            upsert_index_features(db, records)
        output.extend(records)
    status = "OK" if output else "PARTIAL"
    return {
        "flow": "index-features-daily" if start == end else "index-features-backfill",
        "mode": "write" if write else "preview",
        "from": start, "to": end, **index_scope_summary(resolved, requested),
        "source_rows": source_counts, "feature_row_count": len(output),
        "rows": output if not write else None, "status": status,
    }


def run_index_features_preview(date: str, indexes=None, *, db=None) -> dict[str, Any]:
    return _run(date, date, indexes, db=db, write=False)


def run_index_features_daily(date: str, indexes=None, *, db=None) -> dict[str, Any]:
    return _run(date, date, indexes, db=db, write=True)


def run_index_features_backfill(from_date: str, to_date: str, indexes=None, *, db=None) -> dict[str, Any]:
    return _run(from_date, to_date, indexes, db=db, write=True)
