"""Supabase persistence and paginated read boundary for Analog EOD evidence."""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Iterable

from src.utils.time_utils import app_now_iso


class AnalogRepository:
    def __init__(self, client: Any, *, page_size: int = 1000):
        self.client = client
        self.page_size = page_size

    def _pages(self, make_query) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = make_query().range(offset, offset + self.page_size - 1).execute().data or []
            rows.extend(page)
            if len(page) < self.page_size:
                return rows
            offset += len(page)

    @staticmethod
    def _safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: AnalogRepository._safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [AnalogRepository._safe(item) for item in value]
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    def list_profiles(self) -> list[dict[str, Any]]:
        return self._pages(lambda: self.client.table("stock_analog_profiles").select("*").order("profile_code").order("version"))

    def get_profile(self, code: str, version: int) -> dict[str, Any] | None:
        rows = self.client.table("stock_analog_profiles").select("*").eq("profile_code", code).eq("version", version).limit(1).execute().data or []
        return rows[0] if rows else None

    def register_profile(self, row: dict[str, Any]) -> None:
        existing = self.get_profile(row["profile_code"], row["version"])
        if existing and existing.get("config_hash") != row["config_hash"]:
            raise ValueError("CONFIG_HASH_MISMATCH: registered profile identity is immutable")
        if existing:
            row = {
                **row,
                "status": existing["status"],
                "registered_at": existing["registered_at"],
                "status_changed_at": existing["status_changed_at"],
            }
        self.client.table("stock_analog_profiles").upsert(self._safe(row), on_conflict="profile_code,version").execute()

    def upsert_snapshots(self, rows: Iterable[dict[str, Any]]) -> int:
        now = app_now_iso()
        values = []
        for source in rows:
            row = dict(source)
            row["evaluation_status"] = row.pop("status")
            row["invalid_reason_codes"] = row.pop("invalid_reasons")
            row.update(created_at=now, updated_at=now)
            values.append(self._safe(row))
        for start in range(0, len(values), self.page_size):
            self.client.table("stock_analog_snapshots").upsert(values[start:start+self.page_size], on_conflict="profile_code,version,config_hash,symbol,timeframe,checkpoint,trading_session").execute()
        return len(values)

    def resolve_snapshot_ids(self, *, code: str, version: int, config_hash: str, symbols: list[str], start: str, end: str) -> list[dict[str, Any]]:
        return self._pages(lambda: self.client.table("stock_analog_snapshots").select("id,config_hash,symbol,trading_session").eq("profile_code", code).eq("version", version).eq("config_hash", config_hash).in_("symbol", symbols).eq("timeframe", "1d").eq("checkpoint", "EOD").gte("trading_session", start).lte("trading_session", end).order("trading_session"))

    def upsert_outcomes(self, rows: Iterable[dict[str, Any]]) -> int:
        now = app_now_iso()
        values = []
        for source in rows:
            row = dict(source)
            row["unavailable_reason"] = row.pop("reason", None)
            row.update(created_at=now, updated_at=now)
            values.append(self._safe(row))
        for start in range(0, len(values), self.page_size):
            self.client.table("stock_analog_outcomes").upsert(values[start:start+self.page_size], on_conflict="snapshot_id,horizon_sessions").execute()
        return len(values)

    def replace_scope(self, **scope: Any) -> int:
        symbols, start, end = scope["symbols"], scope["start"], scope["end"]
        if not symbols or not start or not end:
            raise ValueError("replace requires exact non-empty symbols and date range")
        # ON DELETE CASCADE removes outcomes in exactly the selected snapshot scope.
        result = self.client.table("stock_analog_snapshots").delete().eq("profile_code", scope["code"]).eq("version", scope["version"]).eq("config_hash", scope["config_hash"]).in_("symbol", symbols).eq("timeframe", "1d").eq("checkpoint", "EOD").gte("trading_session", start).lte("trading_session", end).execute()
        return len(result.data or [])

    def fetch_snapshots(self, *, code: str, version: int, config_hash: str, symbol: str, through: date) -> list[dict[str, Any]]:
        return self._pages(lambda: self.client.table("stock_analog_snapshots").select("*").eq("profile_code", code).eq("version", version).eq("config_hash", config_hash).eq("symbol", symbol).eq("timeframe", "1d").eq("checkpoint", "EOD").lte("trading_session", through.isoformat()).order("trading_session"))

    def fetch_outcomes(self, snapshot_ids: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for start in range(0, len(snapshot_ids), 200):
            ids = snapshot_ids[start:start+200]
            if ids:
                rows.extend(self._pages(lambda ids=ids: self.client.table("stock_analog_outcomes").select("*").in_("snapshot_id", ids).order("snapshot_id").order("horizon_sessions")))
        return rows

    def persist_query(self, query: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
        """Invoke one transactional, idempotent database operation."""
        response = self.client.rpc("persist_analog_query_v1", {"p_query": self._safe(query), "p_matches": self._safe(matches)}).execute()
        data = response.data or []
        return data[0] if isinstance(data, list) and data else data

    def insert_validation(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self.client.table("stock_analog_validation_runs").insert(self._safe(row)).execute().data or []
        return rows[0] if rows else row

    def get_validation(self, validation_id: str) -> dict[str, Any] | None:
        rows = self.client.table("stock_analog_validation_runs").select("*").eq("id", validation_id).limit(1).execute().data or []
        return rows[0] if rows else None

    def insert_review(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = self.client.table("stock_analog_profile_reviews").insert(self._safe(row)).execute().data or []
        return rows[0] if rows else row

    def latest(self, symbol: str, checkpoint: str = "EOD") -> dict[str, Any] | None:
        rows = self.client.table("stock_analog_queries").select("*").eq("symbol", symbol).eq("checkpoint", checkpoint).order("as_of_session", desc=True).limit(1).execute().data or []
        return rows[0] if rows else None

    def query_detail(self, query_id: str) -> dict[str, Any] | None:
        rows = self.client.table("stock_analog_queries").select("*").eq("id", query_id).limit(1).execute().data or []
        if not rows:
            return None
        matches = self._pages(lambda: self.client.table("stock_analog_query_matches").select("*").eq("query_id", query_id).order("rank"))
        return {**rows[0], "matches": matches}
