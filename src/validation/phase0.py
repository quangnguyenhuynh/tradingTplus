"""Read-only Phase 0 schema, payload-lineage, and sample reconciliation checks."""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from src.pipeline.daily_mapper import build_stock_daily_record
from src.pipeline.intraday_mapper import build_intraday_records

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = ZoneInfo("UTC")
STATUS_ORDER = {"PASS": 0, "WARNING": 1, "UNKNOWN": 2, "FAIL": 3}
OHLCV = ("open", "high", "low", "close", "volume")


def _result(status: str, check: str, **details: Any) -> dict[str, Any]:
    return {"status": status, "check": check, **details}


def overall_status(results: Iterable[dict[str, Any]]) -> str:
    statuses = [row["status"] for row in results]
    return max(statuses, key=STATUS_ORDER.get) if statuses else "UNKNOWN"


def verify_schema(connection: Any) -> dict[str, Any]:
    """Inspect PostgreSQL catalogs only; this function never invokes the RPC."""
    checks: list[dict[str, Any]] = []
    with connection.cursor() as cursor:
        cursor.execute("""
          select data_type, is_nullable, column_default
          from information_schema.columns
          where table_schema='public' and table_name='raw_intraday'
            and column_name='payload'
        """)
        row = cursor.fetchone()
        checks.append(_result(
            "PASS" if row == ("jsonb", "YES", None) else "FAIL",
            "raw_intraday.payload",
            observed=row,
            expected=["jsonb", "YES", None],
        ))
        cursor.execute("""
          select p.prosecdef, p.proconfig,
            has_function_privilege('service_role', p.oid, 'execute'),
            has_function_privilege('anon', p.oid, 'execute'),
            has_function_privilege('authenticated', p.oid, 'execute'),
            has_function_privilege('public', p.oid, 'execute')
          from pg_proc p join pg_namespace n on n.oid=p.pronamespace
          where n.nspname='public' and p.proname='replace_features_atomic'
            and pg_get_function_identity_arguments(p.oid) =
              'p_symbol text, p_timeframe text, p_start_utc timestamp with time zone, p_end_exclusive_utc timestamp with time zone, p_replacement_rows jsonb'
        """)
        function_row = cursor.fetchone()
        safe_search_path = bool(
            function_row and function_row[1]
            and any(value in {'search_path=""', 'search_path='} for value in function_row[1])
        )
        function_ok = bool(function_row and function_row[0] and safe_search_path
                           and function_row[2] and not any(function_row[3:]))
        checks.append(_result(
            "PASS" if function_ok else "FAIL",
            "replace_features_atomic security",
            exists=function_row is not None,
            security_definer=bool(function_row and function_row[0]),
            search_path=(function_row[1] if function_row else None),
            service_role_execute=bool(function_row and function_row[2]),
            anon_execute=bool(function_row and function_row[3]),
            authenticated_execute=bool(function_row and function_row[4]),
            public_execute=bool(function_row and function_row[5]),
        ))
        cursor.execute("""
          select indexname, indexdef from pg_indexes
          where schemaname='public' and tablename='features'
        """)
        indexes = cursor.fetchall()
        matching = []
        for name, definition in indexes:
            normalized = definition.lower().replace('"', '').replace(" ", "")
            if "uniqueindex" in normalized and "(symbol,timeframe,time)" in normalized:
                matching.append(name)
        checks.append(_result(
            "PASS" if matching else "FAIL",
            "features unique index",
            matching_indexes=matching,
            expected_columns=["symbol", "timeframe", "time"],
        ))
    return {"status": overall_status(checks), "checks": checks, "read_only": True}


def _vn_bounds(trading_date: date) -> tuple[str, str]:
    start = datetime.combine(trading_date, time.min, tzinfo=VN_TZ).astimezone(UTC)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def check_intraday_payload(client: Any, *, symbol: str | None = None,
                            trading_date: date | None = None) -> dict[str, Any]:
    """Find a bounded non-null payload sample; historical NULLs are informational."""
    query = client.table("stock_raw_intraday").select("symbol,time,payload,fetched_at")
    if symbol:
        query = query.eq("symbol", symbol.upper())
    if trading_date:
        start, end = _vn_bounds(trading_date)
        query = query.gte("time", start).lt("time", end)
    rows = (query.order("fetched_at", desc=True).limit(100).execute().data or [])
    non_null = next((row for row in rows if row.get("payload") is not None), None)
    null_count = sum(row.get("payload") is None for row in rows)
    if non_null:
        return _result("PASS", "intraday payload sample", sample={
            "symbol": non_null.get("symbol"), "time": non_null.get("time"),
            "fetched_at": non_null.get("fetched_at"),
        }, inspected_rows=len(rows), historical_null_rows=null_count,
                       historical_null_policy="EXPECTED_NO_BACKFILL", read_only=True)
    return _result("UNKNOWN", "intraday payload sample", inspected_rows=len(rows),
                   historical_null_rows=null_count,
                   reason="No non-null payload exists in the bounded selected sample",
                   historical_null_policy="EXPECTED_NO_BACKFILL", read_only=True)


def numeric_equal(left: Any, right: Any, tolerance: float) -> bool:
    if left is None or right is None:
        return left is right
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return left == right
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, abs_tol=tolerance, rel_tol=tolerance)


def compare_fields(expected: dict[str, Any], actual: dict[str, Any], fields: Iterable[str],
                   tolerance: float) -> list[dict[str, Any]]:
    return [{"field": field, "expected": expected.get(field), "actual": actual.get(field),
             "match": numeric_equal(expected.get(field), actual.get(field), tolerance)}
            for field in fields]


def _one(client: Any, table: str, columns: str, filters: list[tuple[str, str, Any]],
         *, order: tuple[str, bool] | None = None) -> dict[str, Any] | None:
    query = client.table(table).select(columns)
    for operation, field, value in filters:
        query = getattr(query, operation)(field, value)
    if order:
        query = query.order(order[0], desc=order[1])
    rows = query.limit(1).execute().data or []
    return rows[0] if rows else None


def reconcile_sample(client: Any, *, symbol: str, trading_date: date, timeframe: str,
                     timestamp: str | None = None, tolerance: float = 1e-6) -> dict[str, Any]:
    """Reconcile one bounded persisted raw→clean→feature sample without writes."""
    symbol = symbol.upper()
    if timeframe not in {"1d", "15m", "60m"}:
        raise ValueError("timeframe must be one of: 1d, 15m, 60m")
    start, end = _vn_bounds(trading_date)
    comparisons: list[dict[str, Any]] = []
    missing: list[str] = []

    if timeframe == "1d":
        raw = _one(client, "stock_raw_daily", "symbol,trading_date,payload", [("eq", "symbol", symbol), ("eq", "trading_date", trading_date.isoformat())])
        clean = _one(client, "stock_daily", "*", [("eq", "symbol", symbol), ("eq", "trading_date", trading_date.isoformat())])
        feature = _one(client, "stock_features", "symbol,timeframe,time,open,high,low,close,volume,value",
                       [("eq", "symbol", symbol), ("eq", "timeframe", "1d"), ("gte", "time", start), ("lt", "time", end)])
        if not raw or not isinstance(raw.get("payload"), dict): missing.append("raw_daily.payload")
        if not clean: missing.append("stock_daily")
        if not feature: missing.append("features")
        if not missing:
            mapped = build_stock_daily_record(symbol, trading_date.strftime("%d/%m/%Y"), raw["payload"])
            daily_fields = ("open_price", "highest_price", "lowest_price", "close_price", "total_traded_vol", "total_traded_value")
            comparisons += [{"layer": "raw_to_clean", **row} for row in compare_fields(mapped or {}, clean, daily_fields, tolerance)]
            expected_feature = {"open": clean.get("open_price"), "high": clean.get("highest_price"),
                                "low": clean.get("lowest_price"), "close": clean.get("close_price"),
                                "volume": clean.get("total_traded_vol"), "value": clean.get("total_traded_value")}
            comparisons += [{"layer": "clean_to_feature", **row} for row in compare_fields(expected_feature, feature, (*OHLCV, "value"), tolerance)]
    else:
        feature_filters = [("eq", "symbol", symbol), ("eq", "timeframe", timeframe), ("gte", "time", start), ("lt", "time", end)]
        if timestamp:
            feature_filters = [("eq", "symbol", symbol), ("eq", "timeframe", timeframe), ("eq", "time", timestamp)]
        feature = _one(client, "stock_features", "symbol,timeframe,time,open,high,low,close,volume,value", feature_filters, order=("time", True))
        if not feature: missing.append("features")
        if not missing:
            bucket_start = feature["time"]
            bucket_end = (datetime.fromisoformat(bucket_start.replace("Z", "+00:00")) + timedelta(minutes=int(timeframe[:-1]))).isoformat()
            clean_rows = (client.table("stock_intraday").select("symbol,timeframe,time,open,high,low,close,volume,value")
                          .eq("symbol", symbol).eq("timeframe", "1m").gte("time", bucket_start).lt("time", bucket_end)
                          .order("time").limit(60).execute().data or [])
            if not clean_rows: missing.append("stock_intraday")
            else:
                aggregate = {"open": clean_rows[0].get("open"), "high": max(row["high"] for row in clean_rows if row.get("high") is not None),
                             "low": min(row["low"] for row in clean_rows if row.get("low") is not None), "close": clean_rows[-1].get("close"),
                             "volume": sum(row.get("volume") or 0 for row in clean_rows), "value": sum(row.get("value") or 0 for row in clean_rows)}
                comparisons += [{"layer": "clean_to_feature", **row} for row in compare_fields(aggregate, feature, (*OHLCV, "value"), tolerance)]
                raw = _one(client, "stock_raw_intraday", "symbol,time,payload,open,high,low,close,volume",
                           [("eq", "symbol", symbol), ("eq", "time", clean_rows[0]["time"])])
                if not raw or not isinstance(raw.get("payload"), dict): missing.append("raw_intraday.payload")
                else:
                    _, mapped_rows = build_intraday_records(symbol, trading_date.strftime("%d/%m/%Y"), None, [raw["payload"]])
                    if not mapped_rows: missing.append("mapped raw_intraday.payload")
                    else: comparisons += [{"layer": "raw_to_clean", **row} for row in compare_fields(mapped_rows[0], clean_rows[0], OHLCV, tolerance)]

    status = "UNKNOWN" if missing else ("FAIL" if any(not row["match"] for row in comparisons) else "PASS")
    return _result(status, "sample reconciliation", symbol=symbol, date=trading_date.isoformat(),
                   timeframe=timeframe, feature_time=(feature.get("time") if feature else None),
                   tolerance=tolerance, comparisons=comparisons, missing=missing, read_only=True)
