"""Read-only end-of-day dry run for SSI ingest plus feature calculation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from src.engine.feature_calculator import aggregate_timeframe, compute_daily_features, compute_intraday_features
from src.engine.feature_engine import FEATURE_COLUMNS, _normalize_timeframes
from src.pipeline.daily_fetcher import fetch_daily_price
from src.pipeline.daily_mapper import build_raw_daily_record, build_stock_daily_record
from src.pipeline.intraday_fetcher import fetch_intraday_candles
from src.pipeline.intraday_mapper import build_intraday_records
from src.ssi.api import SSIApi

VN_TZ = timezone(timedelta(hours=7))
DEFAULT_SYMBOLS = ["SSI"]
DEFAULT_TIMEFRAMES = ["1m", "5m", "15m"]
FEATURE_PREVIEW_COLUMNS = [
    "time",
    "close",
    "volume",
    "value",
    "return_1m",
    "return_5m",
    "return_15m",
    "ema9",
    "ema20",
    "ema50",
    "rsi14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "volume_ratio",
    "value_ratio",
    "vwap_intraday",
    "close_above_vwap",
    "close_above_high_20",
    "close_below_low_20",
]


def latest_previous_weekday(now: datetime | None = None) -> str:
    """Return latest previous Monday-Friday date in DD/MM/YYYY format."""
    current = now or datetime.now(VN_TZ)
    day = current.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.strftime("%d/%m/%Y")


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        if value.tzinfo is not None:
            return value.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, (list, dict, tuple)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def _records_for_json(df: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    if df.empty:
        return []
    present_columns = [column for column in columns if column in df.columns]
    rows = df[present_columns].tail(5).copy()
    result: list[dict[str, Any]] = []
    for row in rows.to_dict("records"):
        result.append({key: _json_safe(value) for key, value in row.items()})
    return result


def _stock_daily_mapped_fields(stock_daily_record: dict[str, Any] | None) -> dict[str, Any]:
    if not stock_daily_record:
        return {}
    return {key: value for key, value in stock_daily_record.items() if key != "raw"}


def _build_symbol_summary(ssi: SSIApi, date: str, symbol: str, timeframes: list[str]) -> dict[str, Any]:
    daily = fetch_daily_price(ssi, symbol, date)
    raw_daily_record = build_raw_daily_record(symbol, date, daily) if daily else None
    stock_daily_record = build_stock_daily_record(symbol, date, daily) if daily else None

    summary: dict[str, Any] = {
        "date": date,
        "symbol": symbol,
        "daily_found": bool(daily),
        "intraday_candle_count": 0,
        "first_candle_time": None,
        "last_candle_time": None,
        "raw_daily_built": raw_daily_record is not None,
        "stock_daily_mapped_fields": _stock_daily_mapped_fields(stock_daily_record),
        "feature_timeframes_calculated": [],
        "feature_row_count_by_timeframe": {},
        "feature_preview_by_timeframe": {},
        "warnings": [],
    }

    if not daily:
        summary["warnings"].append(f"{symbol}: missing daily price; skipped feature calculation")
        return summary

    candles = fetch_intraday_candles(ssi, symbol, date)
    summary["intraday_candle_count"] = len(candles)
    if candles:
        summary["first_candle_time"] = candles[0].get("Time")
        summary["last_candle_time"] = candles[-1].get("Time")
    else:
        summary["warnings"].append(f"{symbol}: missing intraday candles; skipped feature calculation")
        return summary

    raw_intraday_records, stock_intraday_records = build_intraday_records(symbol, date, daily, candles)
    summary["raw_intraday_record_count"] = len(raw_intraday_records)
    summary["stock_intraday_record_count"] = len(stock_intraday_records)

    if not stock_intraday_records:
        summary["warnings"].append(f"{symbol}: no valid stock_intraday rows after mapping; skipped feature calculation")
        return summary

    source_df = pd.DataFrame(stock_intraday_records)
    daily_df = pd.DataFrame([stock_daily_record]) if stock_daily_record else None
    last_feature_df = pd.DataFrame()
    for timeframe in _normalize_timeframes(timeframes):
        if timeframe == "1d":
            feature_df = compute_daily_features(daily_df) if daily_df is not None else pd.DataFrame()
        else:
            aggregated_df = aggregate_timeframe(source_df, timeframe)
            feature_df = compute_intraday_features(aggregated_df, timeframe=timeframe, daily_df=daily_df) if not aggregated_df.empty else aggregated_df
        last_feature_df = feature_df
        row_count = len(feature_df)
        summary["feature_timeframes_calculated"].append(timeframe)
        summary["feature_row_count_by_timeframe"][timeframe] = row_count
        summary["feature_preview_by_timeframe"][timeframe] = _records_for_json(feature_df, FEATURE_PREVIEW_COLUMNS)

    missing_feature_columns = [column for column in FEATURE_COLUMNS if column not in last_feature_df.columns] if summary["feature_timeframes_calculated"] else []
    if missing_feature_columns:
        summary["warnings"].append(f"{symbol}: feature calculation missing columns: {missing_feature_columns}")

    return summary


def _print_pretty(summary: dict[str, Any]) -> None:
    print(f"EOD dry run date: {summary['date']}")
    print("Safety: read-only run, no Supabase upsert/write methods are called.")
    for symbol_summary in summary["symbols"]:
        print("=" * 80)
        print(f"Symbol: {symbol_summary['symbol']}")
        print(f"Daily found: {'yes' if symbol_summary['daily_found'] else 'no'}")
        print(f"Intraday candle count: {symbol_summary['intraday_candle_count']}")
        print(f"First candle time: {symbol_summary['first_candle_time']}")
        print(f"Last candle time: {symbol_summary['last_candle_time']}")
        if symbol_summary["warnings"]:
            for warning in symbol_summary["warnings"]:
                print(f"⚠️ {warning}")
        print("Stock daily mapped fields:")
        mapped = symbol_summary["stock_daily_mapped_fields"]
        if mapped:
            print(json.dumps(mapped, ensure_ascii=False, indent=2, default=str))
        else:
            print("  <none>")
        print(f"Feature timeframes calculated: {symbol_summary['feature_timeframes_calculated']}")
        for timeframe in symbol_summary["feature_timeframes_calculated"]:
            row_count = symbol_summary["feature_row_count_by_timeframe"].get(timeframe, 0)
            print(f"\n[{timeframe}] feature rows: {row_count}")
            preview = symbol_summary["feature_preview_by_timeframe"].get(timeframe, [])
            if preview:
                print(pd.DataFrame(preview).to_string(index=False))
            else:
                print("  <no feature rows>")


def run_eod_dry_run(
    date: str | None,
    symbols: list[str] | None,
    timeframes: list[str] | None,
    json_output: bool = False,
) -> dict[str, Any]:
    """Run SSI ingest + feature calculation in memory without DB writes."""
    target_date = date or latest_previous_weekday()
    requested_symbols = [symbol.upper() for symbol in (symbols or DEFAULT_SYMBOLS)]
    requested_timeframes = list(timeframes or DEFAULT_TIMEFRAMES)
    _normalize_timeframes(requested_timeframes)

    ssi = SSIApi()
    summary = {
        "date": target_date,
        "symbols_requested": requested_symbols,
        "timeframes_requested": requested_timeframes,
        "read_only": True,
        "symbols": [
            _build_symbol_summary(ssi, target_date, symbol, requested_timeframes)
            for symbol in requested_symbols
        ],
    }

    if json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        _print_pretty(summary)
    return summary
