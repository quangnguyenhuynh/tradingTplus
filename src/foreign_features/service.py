"""Application service for scoped foreign feature calculations and report RPCs."""
from __future__ import annotations

from decimal import Decimal
from datetime import date as Date
from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import parse_ddmmyyyy, validate_not_future
from src.pipeline.symbol_scope import resolve_active_symbol_scope, normalize_symbol_scope

from .calendar import TradingCalendar, build_calendar, load_calendar
from .calculator import FORMULA_VERSION, calculate_symbol
from .loader import load_rows, load_session_dates
from .persistence import load_existing, upsert


def _json_safe(row: dict[str, Any]) -> dict[str, Any]:
    return {key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()}


def _dates(from_date: str, to_date: str, calendar: TradingCalendar) -> list[str]:
    return [day for day in calendar.sessions if from_date <= day <= to_date]


def _calendar_from_stock_daily(db: Any, symbols: list[str], start: str, end: str) -> TradingCalendar | None:
    sessions = load_session_dates(db, None, end=end)
    if not sessions:
        return None
    return build_calendar(list(sessions), "stock_daily", "scope")


def _resolve_calendar(db: Any, symbols: list[str], start: str, end: str, calendar_file: str | None) -> TradingCalendar | None:
    file_calendar = load_calendar(calendar_file)
    if file_calendar is not None:
        return file_calendar
    return _calendar_from_stock_daily(db, symbols, start, end)


def _run(from_value: str, to_value: str, symbols, calendar_file: str | None, *, db=None, write=False, mode="target") -> dict[str, Any]:
    start, end = parse_ddmmyyyy(from_value), parse_ddmmyyyy(to_value)
    if start.date > end.date:
        raise ValueError("--from must be on or before --to")
    validate_not_future(end)
    db = db or SupabaseClient()
    resolved, requested, unknown = resolve_active_symbol_scope(db, symbols)
    calendar = _resolve_calendar(db, resolved, start.iso, end.iso, calendar_file)
    summary: dict[str, Any] = {"requested": len(resolved), "processed": 0, "written": 0, "invalid": 0, "stale": 0, "insufficient_history": 0, "window_unverified": 0, "errors": [], "unknown_symbols": unknown, "from": start.iso, "to": end.iso, "formula_version": FORMULA_VERSION, "mode": mode, "calendar_source": calendar.source if calendar else None}
    if unknown:
        summary["invalid"] += len(unknown)
        summary["errors"].append({"reason": "UNKNOWN_OR_INACTIVE_SYMBOLS", "symbols": unknown})
    if not calendar:
        summary.update(status="PARTIAL", window_unverified=len(resolved), reason="WINDOW_UNVERIFIED: stock_daily has no sessions for scope; optionally provide --calendar-file")
        return summary
    output_dates = _dates(start.iso, end.iso, calendar)
    if not output_dates:
        summary.update(status="PARTIAL", reason="No verified sessions in requested range")
        return summary
    context = calendar.through(start.iso, 20)
    rows = load_rows(db, resolved, context[0] if context else start.iso, end.iso) if resolved else []
    grouped: dict[str, list[dict]] = {symbol: [] for symbol in resolved}
    for row in rows:
        grouped.setdefault(str(row["symbol"]).upper(), []).append(row)
    calculated: list[dict] = []
    for symbol in resolved:
        for target in output_dates:
            try:
                feature = calculate_symbol(grouped[symbol], calendar, target)
            except ValueError as exc:
                summary["invalid"] += 1; summary["errors"].append({"symbol": symbol, "date": target, "reason": str(exc)}); continue
            summary["processed"] += 1
            if feature is None:
                summary["invalid"] += 1
                continue
            if feature["quality_status"].get("20", {}).get("status") == "INSUFFICIENT_HISTORY":
                summary["insufficient_history"] += 1
            calculated.append(_json_safe(feature))
    if mode == "incremental" and calculated:
        existing = {(r["symbol"], str(r["trading_date"])): r for r in load_existing(db, resolved, start.iso, end.iso)}
        selected = []
        for row in calculated:
            old = existing.get((row["symbol"], row["trading_date"]))
            if not old or old.get("formula_version") != FORMULA_VERSION or old.get("source_fingerprint") != row["source_fingerprint"]:
                if old: summary["stale"] += 1
                selected.append(row)
        calculated = selected
    if write:
        upsert(db, calculated)
        summary["written"] = len(calculated)
    else:
        summary["rows"] = calculated
    summary["status"] = "PARTIAL" if summary["invalid"] or summary["errors"] else "OK"
    return summary


def preview(date: str, symbol: str, calendar_file: str | None, *, db=None) -> dict[str, Any]:
    return _run(date, date, [symbol], calendar_file, db=db, write=False)


def run_daily(date: str, symbols=None, calendar_file=None, mode="target", *, db=None) -> dict[str, Any]:
    if mode == "incremental":
        parsed = parse_ddmmyyyy(date)
        database = db or SupabaseClient()
        resolved, _, _ = resolve_active_symbol_scope(database, symbols)
        calendar = _resolve_calendar(database, resolved, parsed.iso, parsed.iso, calendar_file)
        affected = calendar.through(parsed.iso, 20) if calendar else []
        start = parse_ddmmyyyy(date) if not affected else type(parsed)(affected[0], Date.fromisoformat(affected[0]))
        return _run(start.ddmmyyyy, date, symbols, calendar_file, db=database, write=True, mode=mode)
    return _run(date, date, symbols, calendar_file, db=db, write=True, mode=mode)


def run_backfill(from_date: str, to_date: str, symbols=None, calendar_file=None, *, db=None) -> dict[str, Any]:
    summary = _run(from_date, to_date, symbols, calendar_file, db=db, write=True, mode="backfill")
    database = db or SupabaseClient()
    end = parse_ddmmyyyy(to_date).iso
    resolved, _, _ = resolve_active_symbol_scope(database, symbols)
    calendar = _resolve_calendar(database, resolved, end, end, calendar_file)
    if calendar and end in calendar.sessions:
        summary["affected_after_range"] = list(calendar.sessions[calendar.sessions.index(end)+1:calendar.sessions.index(end)+20])
    else:
        after_sessions = load_session_dates(database, resolved, start=end) if resolved else ()
        summary["affected_after_range"] = [day for day in after_sessions if day > end][:19]
    return summary


def check(from_date: str, to_date: str, symbols=None, calendar_file=None, *, db=None) -> dict[str, Any]:
    database = db or SupabaseClient()
    summary = _run(from_date, to_date, symbols, calendar_file, db=database, write=False, mode="check")
    calculated = {(r["symbol"], r["trading_date"]): r for r in summary.get("rows", [])}
    if calculated:
        start, end = parse_ddmmyyyy(from_date).iso, parse_ddmmyyyy(to_date).iso
        resolved, _, _ = resolve_active_symbol_scope(database, symbols)
        existing = {(r["symbol"], str(r["trading_date"])): r for r in load_existing(database, resolved, start, end)}
        summary["missing_features"] = sum(key not in existing for key in calculated)
        summary["stale"] = sum(key in existing and (existing[key].get("formula_version") != FORMULA_VERSION or existing[key].get("source_fingerprint") != value["source_fingerprint"]) for key, value in calculated.items())
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
