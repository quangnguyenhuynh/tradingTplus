"""Map an already-fetched inspector page without API or database calls."""
from __future__ import annotations

from typing import Any

from src.data_contracts import get_mapping, map_record
from src.data_contracts.transforms import to_date
from src.intraday_value import calculate_trade_value


def endpoint_mapping(source: str, native_name: str) -> tuple[str, dict[str, Any]] | None:
    for dataset in ("stock_daily", "stock_intraday", "index_daily"):
        mapping = get_mapping(source, dataset)
        if mapping.get("inspector", {}).get("endpoint") == native_name:
            return dataset, mapping
    return None


def _first(values: dict[str, Any], *keys: str) -> Any:
    return next((values[key] for key in keys if values.get(key) not in (None, "")), None)


def _context(dataset: str, row: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    raw = {str(key).casefold(): value for key, value in row.items()}
    request = {str(key).casefold(): value for key, value in params.items()}
    is_index = dataset == "index_daily"
    keys = ("index", "indexcode", "indexid") if is_index else ("symbol", "ticker", "stocksymbol")
    actual = _first(raw, *keys)
    expected = _first(request, *keys)
    if actual is not None and expected is not None and str(actual).upper() != str(expected).upper():
        raise ValueError("response identity differs from requested symbol/index")
    start = _first(request, "from", "fromdate", "tradingdate")
    end = _first(request, "to", "todate", "tradingdate")
    start = to_date(start, {}) if start is not None else None
    end = to_date(end, {}) if end is not None else None
    day = _first(raw, "tradingdate", "date", "tradingtime")
    day = to_date(day, {}) if day is not None else None
    if day is not None and ((start and day < start) or (end and day > end)):
        raise ValueError("response trading date is outside the requested range")
    # A multi-day response must supply its own date; never assign the range start.
    day = day or (start if start == end else None)
    context = {"symbol": actual if actual is not None else expected}
    if day:
        context["date"] = f"{day[8:10]}/{day[5:7]}/{day[:4]}"
    return context


def map_rows(source: str, dataset: str, mapping: dict[str, Any],
             rows: list[Any], params: dict[str, Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    clean, reports = [], []
    prefix = mapping["inspector"].get("prefix")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            clean.append(None)
            reports.append({"record": index + 1, "errors": [{"code": "INVALID_RECORD", "message": "expected JSON object"}]})
            continue
        try:
            context = _context(dataset, row, params)
        except ValueError as exc:
            clean.append(None)
            reports.append({"record": index + 1, "errors": [{"code": "INVALID_CONTEXT", "message": str(exc)}]})
            continue
        # Prefixes qualify exact dictionary aliases; they never alter the raw row.
        record = {f"{prefix}.{key}": value for key, value in row.items()} if prefix else row
        result = map_record(source, dataset, record, context)
        if dataset == "stock_intraday" and result.candidate is not None:
            context["value"] = calculate_trade_value(result.candidate["close"], result.candidate["volume"])
            result = map_record(source, dataset, record, context)
        clean.append(result.candidate)
        reports.append({"record": index + 1, **result.report})
    return clean, reports
