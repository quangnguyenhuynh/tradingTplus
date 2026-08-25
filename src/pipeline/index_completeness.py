"""Completeness reporting for index daily raw and clean layers."""
from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy
from src.pipeline.index_scope import index_scope_summary, resolve_index_scope


def _codes(db: Any, table: str, date_iso: str, scope: list[str]) -> list[str]:
    query = db.client.table(table).select("index_code").eq("trading_date", date_iso).in_("index_code", scope).order("index_code")
    result = db._with_retry(lambda: query.execute(), action_name=f"check {table} completeness")
    return [row["index_code"] for row in (result.data or []) if row.get("index_code")]


def check_index_completeness(date: str | None = None, indexes: list[str] | tuple[str, ...] | None = None, *, db: SupabaseClient | None = None) -> dict[str, Any]:
    date = date or latest_previous_weekday().strftime("%d/%m/%Y")
    db = db or SupabaseClient(); date_iso = parse_ddmmyyyy(date).iso
    resolved, requested = resolve_index_scope(db, indexes)
    raw_codes = _codes(db, "index_raw_daily", date_iso, resolved)
    clean_codes = _codes(db, "index_daily", date_iso, resolved)
    raw_set, clean_set = set(raw_codes), set(clean_codes)
    missing_raw = [code for code in resolved if code not in raw_set]
    missing_clean = [code for code in resolved if code not in clean_set]
    rejected = [code for code in resolved if code in raw_set and code not in clean_set]
    status = "FAILED" if not raw_set and not clean_set else "PARTIAL" if missing_raw or missing_clean else "OK"
    return {"flow": "index-check", "date": date_iso, **index_scope_summary(resolved, requested), "index_raw_daily_count": len(raw_codes), "index_daily_count": len(clean_codes), "missing_raw_indexes": missing_raw, "missing_clean_indexes": missing_clean, "raw_without_clean_indexes": rejected, "status": status}
