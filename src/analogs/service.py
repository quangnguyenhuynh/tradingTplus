"""Application services and lifecycle gates; no HTTP framework required."""

from __future__ import annotations

from typing import Any

from src.utils.time_utils import app_now_iso

from .profile import AnalogProfile


def register_profile(
    repository: Any, profile: AnalogProfile, *, apply: bool = False
) -> dict[str, Any]:
    row = {
        "profile_code": profile.code,
        "version": profile.version,
        "config_hash": profile.config_hash,
        "configuration": profile.config,
        "status": profile.config["status"],
        "registered_at": app_now_iso(),
        "status_changed_at": app_now_iso(),
    }
    if apply:
        repository.register_profile(row)
    return {**row, "dry_run": not apply, "status": "registered" if apply else "dry_run"}


def review_profile(
    repository: Any,
    profile_row: dict[str, Any],
    validation_run: dict[str, Any],
    *,
    reviewer: str,
    decision: str,
    reason: str,
    apply: bool = False,
) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    if (
        profile_row["config_hash"] != validation_run.get("config_hash")
        or validation_run.get("run_type") != "final"
        or validation_run.get("status") != "completed"
    ):
        raise ValueError(
            "approval/rejection requires an exact completed final validation run"
        )
    row = {
        "profile_code": profile_row["profile_code"],
        "version": profile_row["version"],
        "config_hash": profile_row["config_hash"],
        "validation_run_id": validation_run["id"],
        "reviewer": reviewer,
        "decision": decision,
        "reason": reason,
    }
    if apply:
        repository.insert_review(row)
    return {**row, "dry_run": not apply, "status": "recorded" if apply else "dry_run"}


class AnalogReadService:
    """Methods directly usable by a future read-only HTTP adapter."""

    def __init__(self, repository: Any):
        self.repository = repository

    def profile(self, code: str, version: int) -> dict[str, Any] | None:
        return self.repository.get_profile(code, version)

    def latest(self, symbol: str, checkpoint: str = "EOD") -> dict[str, Any] | None:
        return self.repository.latest(symbol.upper(), checkpoint)

    def query(self, query_id: str) -> dict[str, Any] | None:
        return self.repository.query_detail(query_id)
