"""Read-only completeness comparison between clean index rows and index features."""
from __future__ import annotations

from collections import Counter
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_index_date
from src.pipeline.index_scope import index_scope_summary, resolve_index_scope


def _rows(db, table, columns, code, start, end):
    rows = []
    offset = 0
    while True:
        query = (db.client.table(table).select(columns).eq("index_code", code)
                 .gte("trading_date", start).lte("trading_date", end)
                 .order("trading_date").range(offset, offset + 999))
        result = db._with_retry(lambda: query.execute(), action_name=f"check {table} {code}")
        page = result.data or []
        rows.extend(page)
        if len(page) < 1000:
            return rows
        offset += 1000


def _prior_clean_count(db, code, start):
    query = (db.client.table("index_daily").select("trading_date")
             .eq("index_code", code).lt("trading_date", start)
             .order("trading_date", desc=True).limit(59))
    result = db._with_retry(lambda: query.execute(), action_name=f"check warm-up {code}")
    return len(result.data or [])


def check_index_features(from_date: str, to_date: str, indexes=None, *, db=None) -> dict[str, Any]:
    start, end = parse_index_date(from_date).iso, parse_index_date(to_date).iso
    if start > end:
        raise ValueError("--from must be on or before --to")
    db = db or SupabaseClient()
    resolved, requested = resolve_index_scope(db, indexes)
    details = []
    for code in resolved:
        clean = _rows(db, "index_daily", "index_code,trading_date", code, start, end)
        features = _rows(db, "index_features_daily", "*", code, start, end)
        raw = _rows(db, "index_raw_daily", "index_code,trading_date", code, start, end)
        clean_dates = [str(row["trading_date"]) for row in clean]
        feature_dates = [str(row["trading_date"]) for row in features]
        raw_dates = {str(row["trading_date"]) for row in raw}
        clean_set, feature_set = set(clean_dates), set(feature_dates)
        prior_count = _prior_clean_count(db, code, start)
        pre_warm_up = min(len(clean), max(0, 59 - prior_count))
        null_dates = [str(row["trading_date"]) for row in features[pre_warm_up:]
                      if any(value is None for key, value in row.items()
                             if key.startswith("index_") and key not in {"index_code"})]
        details.append({
            "index_code": code, "clean_source_row_count": len(clean),
            "expected_feature_row_count": len(clean_set), "actual_feature_row_count": len(features),
            "missing_dates": sorted(clean_set - feature_set),
            "duplicate_identities": sorted(date for date, count in Counter(feature_dates).items() if count > 1),
            "pre_warm_up_rows": pre_warm_up, "unexpected_nulls_after_warm_up": null_dates,
            "raw_without_clean": sorted(raw_dates - clean_set),
            "insufficient_history": len(clean) < 60,
        })
    partial = any(item["missing_dates"] or item["duplicate_identities"] or item["raw_without_clean"] or item["unexpected_nulls_after_warm_up"] for item in details)
    return {"flow": "index-features-check", "from": start, "to": end,
            **index_scope_summary(resolved, requested), "indexes_detail": details,
            "status": "PARTIAL" if partial else "OK"}
