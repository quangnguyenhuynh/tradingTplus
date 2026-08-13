"""CLI handlers for production and read-only Analog workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .profile import load_source_profile
from .pipeline import daily_run
from .runtime import exact_profile, history_build, hydrate_evidence, inspect, query_persisted, repository_from_environment
from .service import register_profile, review_profile
from .validation import calibrate, walk_forward


def parse_date(value: str):
    return datetime.strptime(value, "%d/%m/%Y").date()


def run(args: Any, repository: Any | None = None) -> dict[str, Any]:
    action = args.analog_command
    source = load_source_profile(
        getattr(args, "profile", None) or "TPLUS_ANALOG_CORE_EOD",
        getattr(args, "version", None) or 1,
        getattr(args, "config_hash", None),
    )
    if action == "profiles" and args.profile_command in {"register", "sync"} and not args.apply:
        return register_profile(None, source, apply=False)
    if action == "query" and (source.config["status"] != "approved" or source.config["distance_threshold"] is None):
        return {"status": "blocked", "profile_code": source.code, "version": source.version, "config_hash": source.config_hash, "reason_codes": ["EXACT_PROFILE_NOT_APPROVED", "DISTANCE_THRESHOLD_NULL"], "persisted": False}
    repository = repository or repository_from_environment()
    if action == "profiles":
        if args.profile_command == "list":
            return {"status": "completed", "profiles": repository.list_profiles(), "persisted": False}
        return register_profile(repository, source, apply=args.apply)
    profile, profile_row = exact_profile(repository, args.profile, args.version, getattr(args, "config_hash", None))
    if action == "history":
        return history_build(repository, profile, symbols=args.symbols, start=parse_date(args.from_date), end=parse_date(args.to_date), mode=args.mode, apply=args.apply, confirm_replace=args.confirm_replace)
    if action == "validate":
        snapshots = []
        for item in sorted({str(value).strip().upper() for value in args.symbols}):
            current, prior = hydrate_evidence(repository, profile, item, parse_date(args.to_date))
            snapshots.extend(prior)
            if current:
                snapshots.append(current)
        if args.run_type == "calibration":
            if not args.thresholds or not args.final_test_start:
                raise ValueError("calibration requires --thresholds and --final-test-start")
            return calibrate(
                source,
                snapshots,
                args.thresholds,
                training_start=parse_date(args.from_date),
                training_end=parse_date(args.to_date),
                final_test_start=parse_date(args.final_test_start),
            )
        return walk_forward(
            profile,
            snapshots,
            start=parse_date(args.from_date),
            end=parse_date(args.to_date),
            run_type=args.run_type,
        )
    if action == "daily":
        return daily_run(
            profile_row,
            symbols=args.symbols,
            session=parse_date(args.date),
            apply=args.apply,
        )
    if action in {"approve", "reject"}:
        validation_row = repository.get_validation(args.validation_run)
        if not validation_row:
            raise ValueError("VALIDATION_RUN_NOT_FOUND")
        return review_profile(
            repository,
            profile_row,
            validation_row,
            reviewer=args.reviewer,
            decision=action,
            reason=args.reason,
            apply=args.apply,
        )
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
