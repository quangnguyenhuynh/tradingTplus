"""Supabase persistence boundary for Analog evidence."""

from __future__ import annotations

from typing import Any, Iterable


class AnalogRepository:
    def __init__(self, client: Any):
        self.client = client

    def list_profiles(self) -> list[dict[str, Any]]:
        return (
            self.client.table("analog_profiles")
            .select("*")
            .order("profile_code")
            .order("version")
            .execute()
            .data
            or []
        )

    def get_profile(self, code: str, version: int) -> dict[str, Any] | None:
        rows = (
            self.client.table("analog_profiles")
            .select("*")
            .eq("profile_code", code)
            .eq("version", version)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def register_profile(self, row: dict[str, Any]) -> None:
        self.client.table("analog_profiles").upsert(
            row, on_conflict="profile_code,version"
        ).execute()

    def upsert_snapshots(self, rows: Iterable[dict[str, Any]]) -> int:
        values = list(rows)
        if values:
            self.client.table("analog_snapshots").upsert(
                values,
                on_conflict="profile_code,version,config_hash,symbol,timeframe,checkpoint,trading_session",
            ).execute()
        return len(values)

    def upsert_outcomes(self, rows: Iterable[dict[str, Any]]) -> int:
        values = list(rows)
        if values:
            self.client.table("analog_outcomes").upsert(
                values, on_conflict="snapshot_id,horizon_sessions"
            ).execute()
        return len(values)

    def replace_scope(
        self,
        *,
        code: str,
        version: int,
        config_hash: str,
        symbols: list[str],
        start: str,
        end: str,
    ) -> int:
        if not symbols or not start or not end:
            raise ValueError("replace requires exact non-empty symbols and date range")
        query = (
            self.client.table("analog_snapshots")
            .delete()
            .eq("profile_code", code)
            .eq("version", version)
            .eq("config_hash", config_hash)
            .in_("symbol", symbols)
            .gte("trading_session", start)
            .lte("trading_session", end)
        )
        return len(query.execute().data or [])

    def insert_validation(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = (
            self.client.table("analog_validation_runs").insert(row).execute().data or []
        )
        return rows[0] if rows else row

    def insert_review(self, row: dict[str, Any]) -> dict[str, Any]:
        rows = (
            self.client.table("analog_profile_reviews").insert(row).execute().data or []
        )
        return rows[0] if rows else row

    def persist_query(
        self, query: dict[str, Any], matches: list[dict[str, Any]]
    ) -> dict[str, Any]:
        inserted = (
            self.client.table("analog_queries").insert(query).execute().data or []
        )
        result = inserted[0] if inserted else query
        query_id = result.get("id")
        if matches:
            self.client.table("analog_query_matches").insert(
                [{**row, "query_id": query_id} for row in matches]
            ).execute()
        return result

    def latest(self, symbol: str, checkpoint: str = "EOD") -> dict[str, Any] | None:
        rows = (
            self.client.table("analog_queries")
            .select("*")
            .eq("symbol", symbol)
            .eq("checkpoint", checkpoint)
            .order("as_of_session", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def query_detail(self, query_id: str) -> dict[str, Any] | None:
        rows = (
            self.client.table("analog_queries")
            .select("*")
            .eq("id", query_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        matches = (
            self.client.table("analog_query_matches")
            .select("*")
            .eq("query_id", query_id)
            .order("rank")
            .execute()
            .data
            or []
        )
        return {**rows[0], "matches": matches}
