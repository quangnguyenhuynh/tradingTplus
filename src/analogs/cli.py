"""CLI handlers for production and read-only Analog workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .profile import load_profile
from .runtime import exact_profile, history_build, inspect, query_persisted, repository_from_environment
from .service import register_profile


def parse_date(value: str):
    return datetime.strptime(value, "%d/%m/%Y").date()


def run(args: Any, repository: Any | None = None) -> dict[str, Any]:
    source = load_profile()
    action = args.analog_command
    if action == "profiles" and args.profile_command in {"register", "sync"} and not args.apply:
        return register_profile(None, source, apply=False)
    if action == "query" and (source.config["status"] != "approved" or source.config["distance_threshold"] is None):
        return {"status": "blocked", "profile_code": source.code, "version": source.version, "config_hash": source.config_hash, "reason_codes": ["EXACT_PROFILE_NOT_APPROVED", "DISTANCE_THRESHOLD_NULL"], "persisted": False}
    if action not in {"profiles", "query"} and (
        getattr(args, "profile", source.code) != source.code
        or getattr(args, "version", source.version) != source.version
        or getattr(args, "config_hash", source.config_hash) != source.config_hash
    ):
        return {"status": "blocked", "reason_codes": ["PROFILE_IDENTITY_MISMATCH"], "profile_code": source.code, "version": source.version, "config_hash": source.config_hash, "symbols": sorted({str(s).upper() for s in getattr(args, "symbols", [])}), "persisted": False}
    repository = repository or repository_from_environment()
    if action == "profiles":
        if args.profile_command == "list":
            return {"status": "completed", "profiles": repository.list_profiles(), "persisted": False}
        return register_profile(repository, source, apply=args.apply)
    profile, _ = exact_profile(repository, args.profile, args.version, getattr(args, "config_hash", None))
    if action == "history":
        return history_build(repository, profile, symbols=args.symbols, start=parse_date(args.from_date), end=parse_date(args.to_date), mode=args.mode, apply=args.apply, confirm_replace=args.confirm_replace)
    symbol = str(args.symbol).strip().upper()
    if not symbol:
        raise ValueError("an explicit symbol is required")
    if action == "query":
        return query_persisted(repository, profile, symbol=symbol, session=parse_date(args.date), apply=args.apply)
    if action == "inspect":
        return inspect(repository, profile, symbol=symbol, session=parse_date(args.date), threshold=args.distance_threshold)
    raise ValueError(f"Analog operation not implemented by this EOD runtime: {action}")


# Backward-compatible name retained for callers outside main.py.
dry_summary = run
