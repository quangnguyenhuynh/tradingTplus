"""Application service for scoped foreign feature calculations and report RPCs."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_ddmmyyyy, validate_not_future
from src.pipeline.symbol_scope import resolve_active_symbol_scope, normalize_symbol_scope

from .calculator import FORMULA_VERSION, FINGERPRINT_FIELDS, calculate_symbol
from .loader import load_following_dates, load_rows
from .persistence import load_existing, upsert


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _deprecated_warning(calendar_file: str | None) -> list[str]:
    return (["DEPRECATED_CALENDAR_FILE_IGNORED: rolling windows use same-symbol stock_daily rows"]
            if calendar_file else [])


def _source_trace(rows: list[dict], feature: dict[str, Any]) -> list[dict[str, Any]]:
    dates = set(feature["quality_status"]["20"]["dates"])
    if len(dates) < 20:
        dates.update(feature["quality_status"]["change_5d"]["current"]["dates"])
        dates.update(feature["quality_status"]["change_5d"]["previous"]["dates"])
    return [
        {field: row.get(field) for field in FINGERPRINT_FIELDS}
        for row in rows if str(row.get("trading_date")) in dates
    ]


def _run(
    from_value: str,
    to_value: str,
    symbols,
    calendar_file: str | None,
    *,
    db=None,
    write: bool = False,
    dry_run: bool = False,
    mode: str = "target",
    show_source: bool = False,
) -> dict[str, Any]:
    start, end = parse_ddmmyyyy(from_value), parse_ddmmyyyy(to_value)
    if start.date > end.date:
        raise ValueError("--from must be on or before --to")
    validate_not_future(end)
    database = db or SupabaseClient()
    resolved, _requested, unknown = resolve_active_symbol_scope(database, symbols)
    summary: dict[str, Any] = {
        "requested": len(resolved), "processed": 0, "would_write": 0, "written": 0,
        "invalid": 0, "stale": 0, "insufficient_history": 0, "errors": [],
        "unknown_symbols": unknown, "from": start.iso, "to": end.iso,
        "formula_version": FORMULA_VERSION, "window_basis": "symbol_rows",
        "mode": mode, "dry_run": bool(dry_run), "warnings": _deprecated_warning(calendar_file),
    }
    if unknown:
        summary["invalid"] += len(unknown)
        summary["errors"].append({"reason": "UNKNOWN_OR_INACTIVE_SYMBOLS", "symbols": unknown})
    if not resolved:
        summary["status"] = "PARTIAL" if unknown else "OK"
        summary["rows"] = []
        return summary

    warmup = 39 if mode == "incremental" else 19
    rows = load_rows(database, resolved, start.iso, end.iso, warmup_rows=warmup)
    grouped: dict[str, list[dict]] = {symbol: [] for symbol in resolved}
    for row in rows:
        grouped.setdefault(str(row["symbol"]).upper(), []).append(row)

    calculated: list[dict[str, Any]] = []
    for symbol in resolved:
        symbol_rows = grouped[symbol]
        range_dates = sorted({str(row["trading_date"]) for row in symbol_rows if start.iso <= str(row["trading_date"]) <= end.iso})
        if mode == "target":
            targets = [start.iso]
        elif mode == "incremental":
            targets = sorted({str(row["trading_date"]) for row in symbol_rows if str(row["trading_date"]) <= end.iso})[-20:]
        else:
            targets = range_dates
        if mode == "target" and start.iso not in range_dates:
            summary["processed"] += 1
            summary["invalid"] += 1
            summary["errors"].append({"symbol": symbol, "date": start.iso, "reason": "NO_SOURCE_FOR_DATE"})
            continue
        for target in targets:
            summary["processed"] += 1
            try:
                feature = calculate_symbol(symbol_rows, target)
            except ValueError as exc:
                summary["invalid"] += 1
                summary["errors"].append({"symbol": symbol, "date": target, "reason": str(exc)})
                continue
            if feature is None:
                summary["invalid"] += 1
                summary["errors"].append({"symbol": symbol, "date": target, "reason": "NO_SOURCE_FOR_DATE"})
                continue
            qualities = feature["quality_status"]
            if qualities["20"]["status"] == "INSUFFICIENT_HISTORY":
                summary["insufficient_history"] += 1
            if any(qualities[key]["status"] in {"INVALID_SOURCE", "PARTIAL"} for key in ("5", "20")):
                summary["invalid"] += 1
                summary["errors"].append({"symbol": symbol, "date": target, "reason": "INVALID_OR_PARTIAL_SOURCE"})
            safe = _json_safe(feature)
            if show_source:
                safe["source_rows"] = _json_safe(_source_trace(symbol_rows, feature))
            calculated.append(safe)

    if mode == "backfill" and calculated:
        existing = {(row["symbol"], str(row["trading_date"])): row for row in load_existing(database, resolved, start.iso, end.iso)}
        summary["stale"] = sum(
            (old := existing.get((row["symbol"], row["trading_date"]))) is not None
            and (old.get("formula_version") != FORMULA_VERSION or old.get("source_fingerprint") != row["source_fingerprint"])
            for row in calculated
        )
    if mode == "incremental" and calculated:
        first_date = min(row["trading_date"] for row in calculated)
        existing = {(row["symbol"], str(row["trading_date"])): row for row in load_existing(database, resolved, first_date, end.iso)}
        selected = []
        for row in calculated:
            old = existing.get((row["symbol"], row["trading_date"]))
            if not old or old.get("formula_version") != FORMULA_VERSION or old.get("source_fingerprint") != row["source_fingerprint"]:
                if old:
                    summary["stale"] += 1
                selected.append(row)
        calculated = selected

    summary["would_write"] = len(calculated)
    if write and not dry_run:
        upsert(database, calculated)
        summary["written"] = len(calculated)
    else:
        summary["rows"] = calculated
    summary["status"] = "PARTIAL" if summary["invalid"] or summary["errors"] else "OK"
    return summary


def preview(date: str, symbol: str, calendar_file: str | None = None, *, show_source=False, db=None) -> dict[str, Any]:
    return _run(date, date, [symbol], calendar_file, db=db, mode="target", show_source=show_source)


def run_daily(date: str, symbols=None, calendar_file=None, mode="target", *, dry_run=False, db=None) -> dict[str, Any]:
    return _run(date, date, symbols, calendar_file, db=db, write=True, dry_run=dry_run, mode=mode)


def run_backfill(from_date: str, to_date: str, symbols=None, calendar_file=None, *, dry_run=False, db=None) -> dict[str, Any]:
    database = db or SupabaseClient()
    summary = _run(from_date, to_date, symbols, calendar_file, db=database, write=True, dry_run=dry_run, mode="backfill")
    # A changed source row can affect up to the next 19 rows of its own symbol.
    resolved, _, _ = resolve_active_symbol_scope(database, symbols)
    following = load_following_dates(database, resolved, parse_ddmmyyyy(to_date).iso) if resolved else {}
    summary["affected_after_range"] = {
        "basis": "next_symbol_rows", "maximum_rows_per_symbol": 19, "dates_by_symbol": following,
        "note": "Run a separately scoped backfill if source history before/inside this range changed.",
    }
    return summary


def check(from_date: str, to_date: str, symbols=None, calendar_file=None, *, db=None) -> dict[str, Any]:
    database = db or SupabaseClient()
    summary = _run(from_date, to_date, symbols, calendar_file, db=database, mode="check")
    calculated = {(row["symbol"], row["trading_date"]): row for row in summary.get("rows", [])}
    start, end = parse_ddmmyyyy(from_date).iso, parse_ddmmyyyy(to_date).iso
    resolved, _, _ = resolve_active_symbol_scope(database, symbols)
    existing = {(row["symbol"], str(row["trading_date"])): row for row in load_existing(database, resolved, start, end)} if resolved else {}
    summary["missing_features"] = sum(key not in existing for key in calculated)
    summary["stale"] = sum(
        key in existing and (existing[key].get("formula_version") != FORMULA_VERSION or existing[key].get("source_fingerprint") != value["source_fingerprint"])
        for key, value in calculated.items()
    )
    if summary["missing_features"] or summary["stale"]:
        summary["status"] = "PARTIAL"
    return summary


def _rpc(db: Any, name: str, params: dict[str, Any]) -> dict[str, Any]:
    response = db._with_retry(lambda: db.client.rpc(name, params).execute(), action_name=name)
    return response.data


def run_ranking_rpc(date: str, ranking_type: str, window: int, sort: str, market=None, symbols=None, limit=20, offset=0, *, db=None):
    parsed = parse_ddmmyyyy(date)
    return _rpc(db or SupabaseClient(), "get_foreign_ranking", {"p_date": parsed.iso, "p_ranking_type": ranking_type, "p_window": window, "p_sort_mode": sort, "p_market": market, "p_symbols": normalize_symbol_scope(symbols), "p_limit": limit, "p_offset": offset})


def run_history_rpc(symbol: str, date: str, limit=20, *, db=None):
    parsed = parse_ddmmyyyy(date)
    normalized = normalize_symbol_scope([symbol])[0]
    return _rpc(db or SupabaseClient(), "get_foreign_symbol_history", {"p_symbol": normalized, "p_to_date": parsed.iso, "p_limit": limit})
