"""Thin CLI handlers for Analog workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .profile import load_profile


def parse_date(value: str):
    return datetime.strptime(value, "%d/%m/%Y").date()


def dry_summary(args: Any) -> dict[str, Any]:
    profile = load_profile()
    base = {
        "profile_code": profile.code,
        "version": profile.version,
        "config_hash": profile.config_hash,
        "dry_run": not getattr(args, "apply", False),
    }
    action = args.analog_command
    if action == "profiles":
        return {**base, "status": "dry_run", "operation": args.profile_command}
    symbols = sorted({s.upper() for s in getattr(args, "symbols", [])})
    result = {**base, "operation": action, "symbols": symbols}
    requested_profile = getattr(args, "profile", profile.code)
    requested_version = getattr(args, "version", profile.version)
    requested_hash = getattr(args, "config_hash", profile.config_hash)
    identity_reasons = []
    if requested_profile != profile.code or requested_version != profile.version:
        identity_reasons.append("PROFILE_IDENTITY_MISMATCH")
    if requested_hash != profile.config_hash:
        identity_reasons.append("CONFIG_HASH_MISMATCH")
    if hasattr(args, "from_date"):
        result["range"] = [args.from_date, args.to_date]
    if hasattr(args, "date"):
        result["date"] = args.date
    if identity_reasons:
        result.update(status="blocked", reason_codes=identity_reasons)
    elif (
        action in {"approve", "reject"} and profile.config["distance_threshold"] is None
    ):
        result.update(status="blocked", reason_codes=["DISTANCE_THRESHOLD_NULL"])
    elif action == "query" and (
        profile.config["status"] != "approved"
        or profile.config["distance_threshold"] is None
    ):
        result.update(
            status="blocked",
            reason_codes=["EXACT_PROFILE_NOT_APPROVED", "DISTANCE_THRESHOLD_NULL"],
        )
    else:
        result["status"] = (
            "dry_run"
            if not getattr(args, "apply", False)
            else "apply_requires_database"
        )
    return result
