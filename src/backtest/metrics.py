"""Transparent aggregate evidence with horizon-specific missing counts."""

from __future__ import annotations

import statistics


def calculate_metrics(records: list[dict], cost_rate: float = 0.0) -> dict:
    result = {"sample_size": len(records), "missing_entry_count": sum(r.get("entry_status") != "available" for r in records), "cost_rate": cost_rate}
    for horizon in (1, 3, 5):
        values = [r[f"h{horizon}_gross_return"] for r in records if r.get(f"h{horizon}_gross_return") is not None]
        net = [value - cost_rate for value in values]
        prefix = f"h{horizon}"
        result[f"{prefix}_sample_size"] = len(values)
        result[f"{prefix}_missing_count"] = len(records) - len(values)
        result[f"{prefix}_gross_return_sum"] = sum(values) if values else None
        result[f"{prefix}_net_return_sum"] = sum(net) if net else None
        result[f"{prefix}_win_rate"] = sum(value > 0 for value in net) / len(net) if net else None
        result[f"{prefix}_average_return"] = statistics.fmean(net) if net else None
        result[f"{prefix}_median_return"] = statistics.median(net) if net else None
        result[f"{prefix}_downside_tail"] = min(net) if net else None
    return result
