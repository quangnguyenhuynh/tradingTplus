"""Pure, Decimal-based foreign EOD rolling feature calculation."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from .calendar import TradingCalendar
from .validator import decimal_value, validate_source_row

FORMULA_VERSION = 1


def _fingerprint(rows: list[dict], sessions: list[str], calendar: TradingCalendar) -> str:
    fields = ("symbol", "trading_date", "foreign_buy_val_total", "foreign_sell_val_total", "net_foreign_val", "total_traded_value")
    values = [[None if row.get(k) is None else str(row.get(k)) for k in fields] for row in rows]
    body = {"formula_version": FORMULA_VERSION, "calendar": calendar.identity, "sessions": sessions, "rows": values}
    return hashlib.sha256(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def _window(rows_by_date: dict[str, dict], sessions: list[str], size: int) -> tuple[dict[str, Any], dict[str, Any]]:
    dates = sessions[-size:]
    quality: dict[str, Any] = {"status": "VALID", "expected_sessions": size, "observed_sessions": 0, "reasons": []}
    if len(dates) < size:
        quality.update(status="INSUFFICIENT_HISTORY", reasons=["INSUFFICIENT_HISTORY"])
        return {}, quality
    rows = [rows_by_date.get(day) for day in dates]
    quality["observed_sessions"] = sum(row is not None for row in rows)
    if any(row is None for row in rows):
        quality.update(status="MISSING_SOURCE", reasons=["MISSING_SOURCE"])
        return {}, quality
    invalid = sorted({reason for row in rows for reason in validate_source_row(row)})
    value_invalid = [reason for reason in invalid if "VOLUME" not in reason and "_VOL_" not in reason]
    if value_invalid:
        quality.update(status="INVALID_SOURCE", reasons=invalid)
    elif invalid:
        # Volume quality is reported independently and does not invalidate
        # otherwise valid value-based metrics.
        quality.update(status="PARTIAL", reasons=invalid)
    def vals(field: str):
        return [decimal_value(row.get(field)) for row in rows]
    b, s, n, v = (vals(field) for field in ("foreign_buy_val_total", "foreign_sell_val_total", "net_foreign_val", "total_traded_value"))
    out: dict[str, Any] = {}
    suffix = f"_{size}d"
    if all(x is not None for x in n) and not any(reason.startswith("NET_VALUE") or "NET_FOREIGN_VAL" in reason for reason in invalid):
        out["net_value" + suffix] = sum(n, Decimal(0))
        out["buy_days" + suffix] = sum(x > 0 for x in n)
        out["sell_days" + suffix] = sum(x < 0 for x in n)
    if all(x is not None for x in b + s):
        out["activity_value" + suffix] = sum(b, Decimal(0)) + sum(s, Decimal(0))
    denominator_ok = all(x is not None and x >= 0 for x in v) and "FOREIGN_ACTIVITY_WITH_ZERO_TURNOVER" not in invalid
    denominator = sum(v, Decimal(0)) if denominator_ok else Decimal(0)
    if denominator > 0 and "net_value" + suffix in out:
        out["net_value_ratio" + suffix] = out["net_value" + suffix] / denominator
    if denominator > 0 and "activity_value" + suffix in out:
        out["activity_ratio" + suffix] = out["activity_value" + suffix] / (Decimal(2) * denominator)
    if not denominator_ok or denominator == 0:
        quality["reasons"].append("DENOMINATOR_INVALID" if not denominator_ok else "DENOMINATOR_ZERO")
    if quality["reasons"] and quality["status"] == "VALID":
        quality["status"] = "PARTIAL"
    return out, quality


def calculate_symbol(rows: list[dict], calendar: TradingCalendar | None, target: str) -> dict[str, Any] | None:
    if calendar is None:
        return None
    duplicates = len({str(r.get("trading_date")) for r in rows}) != len(rows)
    if duplicates:
        raise ValueError("DUPLICATE_SOURCE: duplicate symbol/trading_date rows")
    by_date = {str(row["trading_date"]): row for row in rows}
    current = by_date.get(target)
    current_reasons = validate_source_row(current) if current is not None else []
    current_value_errors = [reason for reason in current_reasons if "VOLUME" not in reason and "_VOL_" not in reason]
    if current is None or current_value_errors:
        return None
    sessions = calendar.through(target, 20)
    result: dict[str, Any] = {"symbol": str(current["symbol"]).upper(), "trading_date": target, "formula_version": FORMULA_VERSION}
    q: dict[str, Any] = {"calendar": {"status": "VERIFIED", "source": calendar.source, "market": calendar.market, "sessions": sessions}}
    for size in (5, 20):
        metrics, quality = _window(by_date, sessions, size)
        result.update(metrics); q[str(size)] = quality
    current5, previous5 = sessions[-5:], sessions[-10:-5]
    cur, cq = _window(by_date, current5, 5); prev, pq = _window(by_date, previous5, 5)
    for metric in ("net_value_ratio_5d", "activity_ratio_5d"):
        if metric in cur and metric in prev:
            result[metric.replace("_5d", "_change_5d")] = cur[metric] - prev[metric]
    q["change_5d"] = {"status": "VALID" if all(k in result for k in ("net_value_ratio_change_5d", "activity_ratio_change_5d")) else "PARTIAL", "current": cq, "previous": pq}
    result["quality_status"] = q
    used = [by_date[d] for d in sessions if d in by_date]
    result["source_window_start"] = sessions[0] if sessions else target
    result["source_fingerprint"] = _fingerprint(used, sessions, calendar)
    return result
