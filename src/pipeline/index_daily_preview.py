"""Read-only SSI DailyIndex preview and terminal rendering."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from src.pipeline.index_daily_fetcher import fetch_index_daily
from src.pipeline.index_daily_mapper import build_index_daily_record
from src.ssi.api import SSIApi


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def _parse_date(value: str) -> date:
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD or DD/MM/YYYY")


def _date_range(single_date: str | None, from_date: str | None, to_date: str | None) -> list[date]:
    if single_date:
        if from_date or to_date:
            raise ValueError("--date cannot be combined with --from/--to")
        return [_parse_date(single_date)]
    if not from_date or not to_date:
        raise ValueError("Provide --date or both --from and --to")
    start, end = _parse_date(from_date), _parse_date(to_date)
    if start > end:
        raise ValueError("--from must not be after --to")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def run_index_daily_preview(
    *,
    indexes: Iterable[str],
    single_date: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    ssi: SSIApi | None = None,
) -> dict[str, Any]:
    """Fetch and normalize DailyIndex payloads without constructing a DB client."""
    codes = list(indexes)
    dates = _date_range(single_date, from_date, to_date)
    client = ssi or SSIApi()
    results: list[dict[str, Any]] = []
    for trading_day in dates:
        request_date = trading_day.strftime("%d/%m/%Y")
        for code in codes:
            payloads = fetch_index_daily(client, code, request_date)
            normalized = [
                record
                for payload in payloads
                if (record := build_index_daily_record(code, request_date, payload)) is not None
            ]
            status = "NO_DATA" if not payloads else "OK" if normalized else "REJECTED"
            results.append(
                {
                    "index_code": code,
                    "trading_date": trading_day.isoformat(),
                    "source": "SSI_DailyIndex",
                    "status": status,
                    "raw": payloads,
                    "records": normalized,
                    "rejected_rows": len(payloads) - len(normalized),
                }
            )
    return {"source": "SSI_DailyIndex", "results": results}


def _display(value: Any) -> str:
    return "-" if value is None else str(value)


def render_index_daily_preview(preview: dict[str, Any], *, raw: bool = False, as_json: bool = False) -> str:
    """Render raw JSON, normalized JSON, or a compact human-readable table."""
    results = preview["results"]
    if raw:
        return json.dumps(
            [
                {
                    "index_code": item["index_code"],
                    "trading_date": item["trading_date"],
                    "source": item["source"],
                    "status": item["status"],
                    "raw": item["raw"],
                }
                for item in results
            ],
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    if as_json:
        return json.dumps(
            [record for item in results for record in item["records"]],
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    lines = [
        "index_code | trading_date | index_value | change | ratio_change | total_vol | total_val | source | status",
        "-" * 112,
    ]
    for item in results:
        if not item["raw"]:
            lines.append(
                f"No SSI index daily data returned for {item['index_code']} on {item['trading_date']}"
            )
            continue
        for record in item["records"]:
            values = (
                record.get("index_code"), record.get("trading_date"), record.get("index_value"),
                record.get("change"), record.get("ratio_change"), record.get("total_vol"),
                record.get("total_val"), item["source"], item["status"],
            )
            lines.append(" | ".join(_display(value) for value in values))
        if item["rejected_rows"]:
            lines.append(
                f"{item['index_code']} {item['trading_date']}: "
                f"{item['rejected_rows']} SSI row(s) rejected because code/date was missing or outside scope"
            )
    return "\n".join(lines)
