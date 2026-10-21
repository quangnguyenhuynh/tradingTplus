"""Read-only SSI index daily preview and terminal rendering."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Iterable

from src.ingest.index_daily.index_daily_fetcher import fetch_index_daily
from src.ingest.shared.date_utils import parse_index_date
from src.providers.ssi.base import DataSourceAdapter
from src.providers.ssi.registry import create_production_adapter


def _date_range(single_date: str | None, from_date: str | None, to_date: str | None) -> list[date]:
    if single_date:
        if from_date or to_date:
            raise ValueError("--date cannot be combined with --from/--to")
        return [parse_index_date(single_date).date]
    if not from_date or not to_date:
        raise ValueError("Provide --date or both --from and --to")
    start, end = parse_index_date(from_date).date, parse_index_date(to_date).date
    if start > end:
        raise ValueError("--from must not be after --to")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def run_index_daily_preview(
    *,
    indexes: Iterable[str],
    single_date: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    ssi: DataSourceAdapter | None = None,
) -> dict[str, Any]:
    """Fetch and normalize index daily payloads without constructing a DB client."""
    codes = list(indexes)
    dates = _date_range(single_date, from_date, to_date)
    client = ssi if ssi is not None else create_production_adapter("index_daily")[1]
    results: list[dict[str, Any]] = []
    for trading_day in dates:
        request_date = trading_day.strftime("%d/%m/%Y")
        for code in codes:
            adapted = fetch_index_daily(client, code, request_date)
            payloads = adapted.raw
            normalized = [row for row in adapted.clean if row is not None]
            mapping_summary = [
                {"raw_field_count": len(payload),
                 "normalized_field_count": len(clean) if clean is not None else 0,
                 "omitted_from_clean": report.get("unused_source_fields", [])}
                for payload, clean, report in zip(payloads, adapted.clean,
                                                 adapted.mapping_report.get("record_reports", []))
            ]
            status = "NO_DATA" if not payloads else "OK" if normalized else "REJECTED"
            results.append(
                {
                    "index_code": code,
                    "trading_date": trading_day.isoformat(),
                    "source": adapted.raw_source or adapted.source,
                    "status": status,
                    "raw": payloads,
                    "records": normalized,
                    "mapping_summary": mapping_summary,
                    "rejected_rows": len(payloads) - len(normalized),
                }
            )
    return {"source": adapted.raw_source or adapted.source, "results": results}


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
                    "mapping_summary": item["mapping_summary"],
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
        "index_code | trading_date | index_value | index_change | index_change_percentage | total_trade_volume | total_trade_value | source | status",
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
                record.get("index_change"), record.get("index_change_percentage"),
                record.get("total_trade_volume"), record.get("total_trade_value"),
                item["source"], item["status"],
            )
            lines.append(" | ".join(_display(value) for value in values))
        for summary in item["mapping_summary"]:
            omitted = ", ".join(summary["omitted_from_clean"]) or "none"
            lines.append(
                "Mapping fields: "
                f"raw={summary['raw_field_count']}, "
                f"normalized={summary['normalized_field_count']}, "
                f"omitted_from_clean={omitted}"
            )
        if item["rejected_rows"]:
            lines.append(
                f"{item['index_code']} {item['trading_date']}: "
                f"{item['rejected_rows']} SSI row(s) rejected because code/date was missing or outside scope"
            )
    return "\n".join(lines)
