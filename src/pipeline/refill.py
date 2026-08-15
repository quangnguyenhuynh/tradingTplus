"""Single-symbol source and feature refill maintenance orchestration."""

from __future__ import annotations

from typing import Any, Callable

from src.features import run_daily_feature_backfill, run_intraday_feature_backfill
from src.pipeline.backfill import run_backfill_pipeline
from src.pipeline.symbol_scope import normalize_symbol_scope


def _normalize_single_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("--symbol must contain exactly one non-blank symbol")
    value = symbol.strip()
    if value.upper() == "ALL" or any(character.isspace() for character in value) or "," in value:
        raise ValueError("--symbol must contain exactly one symbol and cannot be ALL")
    normalized = normalize_symbol_scope([value])
    if normalized is None or len(normalized) != 1:
        raise ValueError("--symbol must contain exactly one symbol")
    return normalized[0]


def _error(stage: str, symbol: str, from_date: str, to_date: str, exc: Exception) -> dict[str, str]:
    message = " ".join(str(exc).split())[:1000] or exc.__class__.__name__
    return {
        "stage": stage,
        "symbol": symbol,
        "from_date": from_date,
        "to_date": to_date,
        "error": message,
    }


def _failed_stage(flow: str, error: dict[str, str]) -> dict[str, Any]:
    return {"flow": flow, "status": "FAILED", "errors": [error]}


def _skipped_stage(flow: str, reason: str) -> dict[str, Any]:
    return {"flow": flow, "status": "SKIPPED", "reason": reason, "errors": []}


def _run_feature_stage(
    *,
    stage: str,
    flow: str,
    runner: Callable[..., dict[str, Any]],
    from_date: str,
    to_date: str,
    symbol: str,
    errors: list[dict[str, str]],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        summary = runner(from_date, to_date, symbols=[symbol], **kwargs)
        status = summary.get("status") if isinstance(summary, dict) else None
        if status not in {"OK", "PARTIAL", "FAILED"}:
            raise ValueError(f"runner returned invalid status: {status!r}")
        return summary
    except Exception as exc:
        context = _error(stage, symbol, from_date, to_date, exc)
        errors.append(context)
        return _failed_stage(flow, context)


def run_refill_pipeline(from_date: str, to_date: str, symbol: str) -> dict[str, Any]:
    """Upsert one symbol's source data, validate it, then refill 1d/15m/60m features."""
    normalized_symbol = _normalize_single_symbol(symbol)
    errors: list[dict[str, str]] = []
    stages: dict[str, dict[str, Any]] = {}

    try:
        source = run_backfill_pipeline(from_date, to_date, symbols=[normalized_symbol])
        source_status = source.get("status") if isinstance(source, dict) else None
        if source_status not in {"OK", "PARTIAL", "FAILED"}:
            raise ValueError(f"runner returned invalid status: {source_status!r}")
    except Exception as exc:
        context = _error("source_backfill", normalized_symbol, from_date, to_date, exc)
        errors.append(context)
        source = _failed_stage("backfill", context)
        source_status = "FAILED"
    stages["source_backfill"] = source

    no_op = source_status == "OK" and source.get("processed_days") == 0
    if no_op:
        reason = "inclusive range contains weekends only; no source or feature rows were written"
        stages["features_daily"] = _skipped_stage("features-daily-backfill", reason)
        stages["features_intraday"] = _skipped_stage("features-intraday-backfill", reason)
        status = "OK"
    elif source_status == "FAILED":
        reason = "source_backfill failed; feature stages require usable clean source data"
        stages["features_daily"] = _skipped_stage("features-daily-backfill", reason)
        stages["features_intraday"] = _skipped_stage("features-intraday-backfill", reason)
        status = "FAILED"
    else:
        stages["features_daily"] = _run_feature_stage(
            stage="features_daily",
            flow="features-daily-backfill",
            runner=run_daily_feature_backfill,
            from_date=from_date,
            to_date=to_date,
            symbol=normalized_symbol,
            errors=errors,
        )
        stages["features_intraday"] = _run_feature_stage(
            stage="features_intraday",
            flow="features-intraday-backfill",
            runner=run_intraday_feature_backfill,
            from_date=from_date,
            to_date=to_date,
            symbol=normalized_symbol,
            errors=errors,
            timeframes=("15m", "60m"),
        )
        feature_statuses = {
            stages["features_daily"]["status"],
            stages["features_intraday"]["status"],
        }
        if feature_statuses == {"FAILED"}:
            status = "FAILED"
        elif source_status == "OK" and feature_statuses == {"OK"}:
            status = "OK"
        else:
            status = "PARTIAL"

    return {
        "flow": "refill",
        "symbol": normalized_symbol,
        "from_date": from_date,
        "to_date": to_date,
        "no_op": no_op,
        "stages": stages,
        "errors": errors,
        "status": status,
    }


__all__ = ["run_refill_pipeline"]
