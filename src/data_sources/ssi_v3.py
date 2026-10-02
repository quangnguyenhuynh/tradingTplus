"""Verified SSI v3 production adapters for stock and index daily datasets."""
from __future__ import annotations

from typing import Any

from src.data_contracts import map_record
from src.data_contracts.derived import apply_derived_fields
from src.data_sources.base import AdapterResult
from src.ssi.v3 import SSIV3Client


class SSIV3Adapter:
    """Fetch and map verified SSI v3 daily capabilities without persistence."""

    source_id = "ssi_v3"

    def __init__(self, client: SSIV3Client | None = None) -> None:
        self.client = client or SSIV3Client()

    def fetch(
        self,
        dataset: str,
        identity: str,
        date: str,
        *,
        context: dict | None = None,
    ) -> AdapterResult:
        if dataset == "stock_daily":
            return self._fetch_stock_daily(identity, date)
        if dataset != "index_daily":
            raise ValueError(f"unsupported SSI v3 production dataset: {dataset}")
        result = self.client.index_summary(identity, date)
        payloads = result.items
        clean: list[dict[str, Any] | None] = []
        reports: list[dict[str, Any]] = []
        for payload in payloads:
            qualified = {f"indexSummary.{key}": value for key, value in payload.items()}
            mapped = map_record("ssi_v3", dataset, qualified, {"index": identity})
            candidate = mapped.candidate
            if candidate is not None and candidate["trading_date"] != _iso_date(date):
                report = {
                    **mapped.report,
                    "records_valid": 0,
                    "records_rejected": 1,
                    "errors": mapped.report["errors"] + [{"code": "REQUEST_SCOPE_MISMATCH"}],
                }
                candidate = None
            else:
                report = mapped.report
            clean.append(candidate)
            reports.append(report)
        errors = [error for report in reports for error in report.get("errors", [])]
        return AdapterResult(
            self.source_id,
            dataset,
            payloads,
            clean,
            errors,
            {
                "source": self.source_id,
                "dataset": dataset,
                "contract_version": "2.0.0",
                "mapping_version": "2.0.0",
                "records_received": len(payloads),
                "records_valid": sum(item is not None for item in clean),
                "records_rejected": sum(item is None for item in clean),
                "record_reports": reports,
            },
        )

    def _fetch_stock_daily(self, symbol: str, date: str) -> AdapterResult:
        payloads = self.client.securities_summary(symbol, date).items
        clean: list[dict[str, Any] | None] = []
        reports: list[dict[str, Any]] = []
        requested_symbol, requested_date = symbol.upper(), _iso_date(date)
        for payload in payloads:
            qualified = {f"summary.{key}": value for key, value in payload.items()}
            mapped = map_record("ssi_v3", "stock_daily", qualified, {})
            candidate = dict(mapped.candidate) if mapped.candidate is not None else None
            report = mapped.report
            if candidate is not None:
                apply_derived_fields("stock_daily", candidate)
                if candidate["symbol"] != requested_symbol or candidate["trading_date"] != requested_date:
                    report = {
                        **report,
                        "records_valid": 0,
                        "records_rejected": 1,
                        "errors": report["errors"] + [{"code": "REQUEST_SCOPE_MISMATCH"}],
                    }
                    candidate = None
                else:
                    candidate["raw"] = payload
            clean.append(candidate)
            reports.append(report)
        errors = [error for report in reports for error in report.get("errors", [])]
        return AdapterResult(
            self.source_id,
            "stock_daily",
            payloads,
            clean,
            errors,
            {
                "source": self.source_id,
                "dataset": "stock_daily",
                "contract_version": "1.1.0",
                "mapping_version": "1.3.0",
                "records_received": len(payloads),
                "records_valid": sum(item is not None for item in clean),
                "records_rejected": sum(item is None for item in clean),
                "record_reports": reports,
                "errors": errors,
            },
        )


def _iso_date(value: str) -> str:
    from src.data_contracts.transforms import to_date

    return to_date(value, {})
