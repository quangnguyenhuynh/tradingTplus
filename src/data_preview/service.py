"""Read-only SSI canonical preview and comparison; this module has no DB imports."""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any

from src.data_contracts import get_contract, get_mapping, map_record
from src.data_contracts.transforms import TRANSFORMS, TransformError
from src.ssi.v3 import SSIV3Client, SSIReadError, securities_summary_params
from src.validation.daily_validator import validate_daily_record

_MISSING = object()


def _lookup(row: dict[str, Any], alias: str) -> tuple[str | None, Any]:
    lookup = {str(key).casefold(): (str(key), value) for key, value in row.items()}
    return lookup.get(alias.casefold(), (None, _MISSING))


def _flatten(endpoint: str, row: dict[str, Any]) -> dict[str, Any]:
    return {f"{endpoint}.{key}": value for key, value in row.items()}


def _safe_params(dataset: str, code: str, date: str, source: str, client: Any = None) -> Any:
    if source == "ssi_v3":
        if dataset == "stock_daily":
            params = securities_summary_params(
                code, date, page_size=getattr(client, "page_size", 1000)
            )
            return {"endpoint": "GET /api/v3/data/securitiesSummary", "params": params}
        if dataset == "stock_intraday":
            return {"endpoint": "GET /api/v3/data/ohlc", "params": {"symbol": code, "from": date + " 00:00:00", "to": date + " 23:59:59", "timeFrame": "1m"}}
        return {"endpoint": "GET /api/v3/data/indexSummary", "params": {"index": code, "tradingDate": date}}
    endpoint = "DailyStockPrice" if dataset == "stock_daily" else ("IntradayOhlc" if dataset == "stock_intraday" else "DailyIndex")
    return {"endpoint": f"SSI v2 {endpoint}", "params": {"symbol_or_index": code, "date": date}}


def _mapping_trace(source: str, dataset: str, row: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    contract = get_contract(dataset)
    mapping = get_mapping(source, dataset)
    clean: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []
    used: set[str] = set()
    for field, spec in contract["fields"].items():
        rule = mapping["fields"].get(field)
        status, raw_state, raw, source_field, warning = "MISSING", "ABSENT", None, None, None
        if not rule or rule.get("unsupported"):
            clean[field] = None
            trace.append({"clean_field": field, "raw_field": None, "raw_state": "NOT_APPLICABLE", "raw_value": None, "rule": None, "clean_value": None, "type": spec["type"], "unit": spec["unit"], "status": "UNVERIFIED", "warning": (rule or {}).get("reason", "No mapping rule")})
            continue
        if "context" in rule:
            source_field = f"request.{rule['context']}"
            raw = context.get(rule["context"], _MISSING)
        elif "constant" in rule:
            source_field, raw = "mapping.constant", rule["constant"]
        else:
            raw = _MISSING
            for alias in rule.get("aliases", []):
                actual, value = _lookup(row, alias)
                if actual is not None:
                    used.add(actual)
                    source_field, raw = actual, value
                    break
            source_field = source_field or (rule.get("aliases") or [None])[0]
        if raw is _MISSING:
            value = None
        elif raw is None:
            raw_state, value = "NULL", None
        elif raw == "":
            raw_state, value = "EMPTY", None
        else:
            raw_state = "PRESENT"
            try:
                value = TRANSFORMS[rule["transform"]](raw, context)
                status = "MAPPED"
            except TransformError as exc:
                value, status, warning = None, "INVALID", str(exc)
        clean[field] = value
        if source == "ssi_v3" and field.startswith("foreign_") and raw_state == "PRESENT" and value == 0:
            warning = "API returned zero; this does not prove that no foreign trading occurred"
        trace.append({"clean_field": field, "raw_field": source_field, "raw_state": raw_state, "raw_value": None if raw is _MISSING else raw, "rule": rule["transform"], "clean_value": value, "type": spec["type"], "unit": spec["unit"], "status": status, "warning": warning})
    if dataset == "stock_intraday" and clean.get("close") is not None and clean.get("volume") is not None:
        from src.intraday_value import calculate_trade_value
        clean["value"] = calculate_trade_value(clean["close"], clean["volume"])
        item = next(entry for entry in trace if entry["clean_field"] == "value")
        item.update(status="DERIVED", rule="round(close * volume)", clean_value=clean["value"], warning="Canonical estimated candle value")
    if dataset == "stock_daily":
        for target, left, right in (("net_foreign_vol", "foreign_buy_vol_total", "foreign_sell_vol_total"), ("net_foreign_val", "foreign_buy_val_total", "foreign_sell_val_total")):
            if clean.get(left) is not None and clean.get(right) is not None:
                clean[target] = clean[left] - clean[right]
                item = next(entry for entry in trace if entry["clean_field"] == target)
                item.update(status="DERIVED", rule=f"{left} - {right}", clean_value=clean[target], warning="Derived only because both normalized inputs are present")
    unmapped = [{"raw_field": key, "raw_value": value, "reason": "UNVERIFIED: no confirmed clean target or intentionally not applicable"} for key, value in row.items() if key not in used]
    return clean, trace, unmapped


def _issues(validation: Any) -> list[dict[str, Any]]:
    return [{"severity": issue.severity, "code": issue.code, "field": issue.field, "message": issue.message, "actual": issue.actual_value, "expected": issue.expected_value} for issue in validation.errors + validation.warnings]


def _fetch_v3(dataset: str, code: str, date: str, client: Any) -> tuple[list[dict[str, Any]], Any, dict[str, Any]]:
    if dataset == "stock_daily":
        page = client.securities_summary(code, date)
        rows = [_flatten("summary", item) for item in page.items]
        endpoint = "securitiesSummary"
    elif dataset == "stock_intraday":
        page = client.ohlc_1m(code, date)
        rows = [_flatten("ohlc", item) for item in page.items]
        endpoint = "ohlc"
    else:
        page = client.index_summary(code, date)
        rows = []
        for item in page.items:
            actual = item.get("index") or item.get("indexCode")
            if actual and str(actual).upper() != code:
                raise SSIReadError("indexSummary identity conflicts with requested single index")
            item = dict(item)
            item.setdefault("index", code); item.setdefault("tradingDate", date)
            rows.append(_flatten("indexSummary", item))
        endpoint = "indexSummary"
    raw = {endpoint: copy.deepcopy(page.raw_pages)}
    return rows, raw, {"pages_fetched": page.pages, "records_fetched": len(page.items), "pagination_complete": getattr(page, "complete", True)}


def _fetch_v2(dataset: str, code: str, date: str, factory: Any = None) -> tuple[list[dict[str, Any]], Any, dict[str, Any]]:
    from src.ssi.api import SSIApi
    with redirect_stdout(sys.stderr):
        client = (factory or SSIApi)()
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
        rows = client.get_daily_price_items(code, day) if dataset == "stock_daily" else (client.get_intraday(code, day) if dataset == "stock_intraday" else client.get_daily_index_items(code, day))
    rows = copy.deepcopy(rows)
    return rows, {"legacy": copy.deepcopy(rows)}, {"pages_fetched": None, "records_fetched": len(rows), "pagination_complete": None}


def _business_key(dataset: str, clean: dict[str, Any]) -> tuple[Any, ...]:
    if dataset == "stock_daily": return clean.get("symbol"), clean.get("trading_date")
    if dataset == "stock_intraday": return clean.get("symbol"), clean.get("time"), clean.get("timeframe")
    return clean.get("index_code"), clean.get("trading_date")


def _one_source(dataset: str, code: str, date: str, source: str, client: Any = None, v2_factory: Any = None) -> dict[str, Any]:
    resolved_client = client or SSIV3Client() if source == "ssi_v3" else None
    rows, raw, fetch = _fetch_v3(dataset, code, date, resolved_client) if source == "ssi_v3" else _fetch_v2(dataset, code, date, v2_factory)
    records, diagnostics = [], []
    context = {"symbol": code, "date": datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")}
    for row in rows:
        original = copy.deepcopy(row)
        clean, trace, unmapped = _mapping_trace(source, dataset, row, context)
        engine_report = None
        if source == "ssi_v2":
            engine_result = map_record(source, dataset, row, context)
            engine_report = engine_result.report
            if engine_result.candidate is not None and engine_result.candidate != clean:
                raise RuntimeError("preview trace differs from shared mapping engine")
        if row != original:
            raise RuntimeError("mapping mutated the raw response")
        validation_issues = []
        if dataset == "stock_daily":
            validation_issues = _issues(validate_daily_record(clean))
            raw_symbol = next((value for key, value in row.items() if key.casefold() in {"symbol", "ticker", "stocksymbol", "summary.symbol"}), None)
            raw_date = next((value for key, value in row.items() if key.casefold() in {"tradingdate", "date", "tradingtime", "summary.tradingdate"}), None)
            try: normalized_raw_date = TRANSFORMS["date"](raw_date, {}) if raw_date not in (None, "") else None
            except TransformError: normalized_raw_date = "INVALID"
            if raw_symbol not in (None, "") and str(raw_symbol).upper() != code:
                validation_issues.append({"severity": "error", "code": "REQUEST_SYMBOL_MISMATCH", "field": "symbol", "message": f"raw symbol {raw_symbol!r} differs from request {code!r}"})
            if normalized_raw_date not in (None, date):
                validation_issues.append({"severity": "error", "code": "REQUEST_DATE_MISMATCH", "field": "trading_date", "message": f"raw date {raw_date!r} differs from request {date!r}"})
            actual = (clean.get("symbol"), clean.get("trading_date"))
            if actual != (code, date):
                validation_issues.append({"severity": "error", "code": "REQUEST_IDENTITY_MISMATCH", "field": "business_key", "message": f"response key {actual!r} differs from request {(code, date)!r}"})
        invalid = any(x["status"] == "INVALID" for x in trace) or any(x["severity"] == "error" for x in validation_issues)
        records.append({"key": _business_key(dataset, clean), "clean": clean, "canonical": clean, "mapping": trace, "fields": [{**x, "status": "UNSUPPORTED" if x["status"] == "UNVERIFIED" else x["status"], "field": x["clean_field"], "source_path": x["raw_field"], "before": x["raw_value"], "after": x["clean_value"], "transform": x["rule"], "reason": x["warning"]} for x in trace], "unmapped_raw_fields": unmapped, "mapping_engine_report": engine_report, "validation": {"status": "INVALID" if invalid else "VALID", "issues": validation_issues}})
    counts = Counter(record["key"] for record in records)
    for key, count in counts.items():
        if count > 1: diagnostics.append({"severity": "error", "code": "DUPLICATE_BUSINESS_KEY", "key": key, "count": count})
    status = "NO_DATA" if not rows else ("INVALID" if diagnostics or any(r["validation"]["status"] == "INVALID" for r in records) else "OK")
    mapping = get_mapping(source, dataset)
    return {"mode": "READ-ONLY — NO DATABASE WRITES", "dataset": dataset, "source": source, "symbol_or_index": code, "requested_date": date, "request": _safe_params(dataset, code, date, source, resolved_client), "fetched_at": datetime.now(timezone.utc).isoformat(), "fetch": {**fetch, "status": "NO_DATA" if not rows else "SUCCESS"}, "contract_version": mapping["contract_version"], "mapping_version": mapping["mapping_version"], "status": status, "records": records, "diagnostics": diagnostics, "raw": raw}


def _verified(record: dict[str, Any] | None, field: str) -> bool:
    if record is None: return True
    trace = next((x for x in record["mapping"] if x["clean_field"] == field), None)
    return trace is None or trace["status"] != "UNVERIFIED"


def _compare(dataset: str, left: dict[str, Any], right: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    a = {tuple(r["key"]): r for r in left["records"]}; b = {tuple(r["key"]): r for r in right["records"]}
    output = []
    for key in sorted(set(a) | set(b), key=str):
        for field in get_contract(dataset)["fields"]:
            ar, br = a.get(key), b.get(key)
            av = ar["clean"].get(field) if ar else None; bv = br["clean"].get(field) if br else None
            if not _verified(ar, field) or not _verified(br, field): status = "UNVERIFIED"
            elif ar is None: status = "MISSING_V2"
            elif br is None: status = "MISSING_V3"
            elif any(next((x["status"] for x in r["mapping"] if x["clean_field"] == field), None) == "INVALID" for r in (ar, br)): status = "INVALID"
            elif av is None and bv is None: status = "BOTH_NULL"
            elif av is None: status = "MISSING_V2"
            elif bv is None: status = "MISSING_V3"
            else: status = "MATCH" if type(av) is type(bv) and av == bv else "DIFFERENT"
            delta = bv - av if isinstance(av, (int, float)) and not isinstance(av, bool) and isinstance(bv, (int, float)) and not isinstance(bv, bool) else None
            output.append({"key": list(key), "clean_field": field, "ssi_v2": av, "ssi_v3": bv, "delta_v3_minus_v2": delta, "status": status, "tolerance": 0})
    return output, dict(Counter(row["status"] for row in output))


def run_preview(dataset: str, code: str, date: str, source: str = "ssi_v3", compare: tuple[str, str] | None = None, client: Any = None, v2_factory: Any = None) -> dict[str, Any]:
    if compare:
        sources, errors = [], []
        for item in compare:
            try: sources.append(_one_source(dataset, code, date, item, client if item == "ssi_v3" else None, v2_factory))
            except Exception as exc: errors.append({"source": item, "type": type(exc).__name__, "message": str(exc)})
        comparison, summary = ([], {})
        by_source = {item["source"]: item for item in sources}
        if "ssi_v2" in by_source and "ssi_v3" in by_source:
            comparison, summary = _compare(dataset, by_source["ssi_v2"], by_source["ssi_v3"])
        bad = errors or any(item["status"] != "OK" for item in sources)
        return {"mode": "READ-ONLY — NO DATABASE WRITES", "dataset": dataset, "symbol_or_index": code, "requested_date": date, "status": "INCOMPLETE" if bad else "OK", "sources": sources, "comparison": comparison, "summary": {"sources_completed": len(sources), "records_v2": len(by_source.get("ssi_v2", {}).get("records", [])), "records_v3": len(by_source.get("ssi_v3", {}).get("records", [])), "fields": summary}, "diagnostics": errors}
    try:
        return _one_source(dataset, code, date, source, client, v2_factory)
    except Exception as exc:
        if dataset != "stock_daily":
            raise
        return {"mode": "READ-ONLY — NO DATABASE WRITES", "dataset": dataset, "source": source, "symbol_or_index": code, "requested_date": date, "status": "ERROR", "records": [], "diagnostics": [{"source": source, "type": type(exc).__name__, "message": str(exc)}]}


def render_preview(result: dict[str, Any], fmt: str = "table", show_raw: bool = False, only_diff: bool = False, show_mapping: bool = False) -> str:
    value = copy.deepcopy(result)
    for source in ([value] if "source" in value else value.get("sources", [])):
        for record in source.get("records", []):
            record.pop("fields", None); record.pop("canonical", None)
        if not show_raw: source.pop("raw", None)
        if not show_mapping:
            for record in source.get("records", []): record.pop("mapping", None)
    if only_diff:
        value["comparison"] = [row for row in value.get("comparison", []) if row["status"] != "MATCH"]
    if fmt == "json": return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    lines = [value["mode"], f"dataset={value['dataset']} code={value.get('symbol_or_index')} date={value['requested_date']} status={value['status']}"]
    for source in ([value] if "source" in value else value.get("sources", [])):
        if "request" not in source:
            continue
        lines.append(f"source={source['source']} endpoint={source['request']['endpoint']} fetch={source['fetch']['status']} records={source['fetch']['records_fetched']} pages={source['fetch']['pages_fetched']} pagination_complete={source['fetch']['pagination_complete']} contract={source['contract_version']} mapping={source['mapping_version']}")
        for record in source["records"]:
            lines.append("clean=" + json.dumps(record["clean"], ensure_ascii=False, default=str))
            if show_mapping:
                lines.append("clean field | raw field | raw state | raw value | rule | clean value | type/unit | status | warning")
                for item in record["mapping"]: lines.append(f"{item['clean_field']} | {item['raw_field']} | {item['raw_state']} | {item['raw_value']!r} | {item['rule']} | {item['clean_value']!r} | {item['type']}/{item['unit']} | {item['status']} | {item['warning'] or ''}")
            for issue in record["validation"]["issues"]: lines.append(f"{issue['severity'].upper()}: {issue['code']} {issue.get('field') or ''} {issue['message']}")
            for item in record["unmapped_raw_fields"]: lines.append(f"UNMAPPED: {item['raw_field']}={item['raw_value']!r} — {item['reason']}")
        if show_raw: lines.append("raw=" + json.dumps(source.get("raw"), ensure_ascii=False, default=str))
    if "comparison" in value:
        lines.append("clean field | v2 | v3 | v3-v2 | status")
        for row in value["comparison"]: lines.append(f"{row['clean_field']} | {row['ssi_v2']} | {row['ssi_v3']} | {row['delta_v3_minus_v2']} | {row['status']}")
        lines.append("summary=" + json.dumps(value["summary"], ensure_ascii=False))
    for error in value.get("diagnostics", []): lines.append("ERROR: " + json.dumps(error, ensure_ascii=False))
    return "\n".join(lines)
