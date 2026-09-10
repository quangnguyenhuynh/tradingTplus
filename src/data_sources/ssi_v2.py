"""Verified SSI v2 adapters for the three production source datasets."""
from __future__ import annotations

from typing import Any

from src.data_sources.base import AdapterResult
from src.ssi.api import SSIApi


class SSIV2Adapter:
    source_id = "ssi_v2"

    def __init__(self, client: SSIApi | None = None) -> None:
        self.client = client or SSIApi()

    # Compatibility surface for existing injected service tests/callers.
    def get_daily_price(self, symbol: str, date: str):
        return self.client.get_daily_price(symbol, date)

    def get_intraday(self, symbol: str, date: str):
        return self.client.get_intraday(symbol, date)

    def get_daily_index_items(self, index_code: str, date: str):
        return self.client.get_daily_index_items(index_code, date)

    def fetch(self, dataset: str, identity: str, date: str, *, context: dict | None = None) -> AdapterResult:
        if dataset == "stock_daily":
            from src.pipeline.daily_mapper import map_stock_daily_record
            payload = self.client.get_daily_price(identity, date)
            raw = [payload] if payload else []
            clean, report = map_stock_daily_record(identity, date, payload) if payload else (None, {})
            return AdapterResult(self.source_id, dataset, raw, [clean] if clean else [], report.get("errors", []), report)
        if dataset == "stock_intraday":
            from src.pipeline.intraday_mapper import daily_context_payload, map_intraday_records
            payloads = self.client.get_intraday(identity, date) or []
            _raw_records, clean, report = map_intraday_records(identity, date, daily_context_payload(context), payloads)
            return AdapterResult(self.source_id, dataset, payloads, clean, report.get("errors", []), report)
        if dataset == "index_daily":
            from src.pipeline.index_daily_mapper import map_index_daily_record
            payloads = self.client.get_daily_index_items(identity, date) or []
            clean: list[dict[str, Any] | None] = []
            reports = []
            for payload in payloads:
                candidate, report = map_index_daily_record(identity, date, payload)
                reports.append(report)
                clean.append(candidate)
            errors = [error for report in reports for error in report.get("errors", [])]
            return AdapterResult(self.source_id, dataset, payloads, clean, errors, {
                "source": self.source_id, "dataset": dataset, "contract_version": "1.0.0",
                "mapping_version": "1.0.0", "records_received": len(payloads),
                "records_valid": sum(item is not None for item in clean),
                "records_rejected": sum(item is None for item in clean),
                "record_reports": reports,
            })
        raise ValueError(f"unsupported dataset: {dataset}")
