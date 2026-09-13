"""Canonical dataset request planning for the read-only SSI API inspector."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from scripts.ssi_api_inspector.endpoints import ParameterError, parse_date, registry
from src.data_contracts.registry import get_mapping
from src.data_sources.registry import Capability, resolve_source, source_capabilities

CLI_DATASETS = {
    "stock-daily": "stock_daily",
    "stock-intraday": "stock_intraday",
    "index-daily": "index_daily",
    "symbol-list": "symbol_list",
    "index-list": "index_list",
}
MAX_DATA_REQUESTS = 100


@dataclass(frozen=True)
class DatasetRequest:
    dataset: str
    symbol: str | None
    index_code: str | None
    date: str | None
    from_date: str | None
    to_date: str | None
    page_index: int
    page_size: int
    ascending: bool | None = None
    board: str | None = None
    market: str | None = None
    exchange: str | None = None


@dataclass(frozen=True)
class PlannedRequest:
    request: DatasetRequest
    params: dict[str, Any]
    label: str


@dataclass(frozen=True)
class DatasetPlan:
    requested_source: str | None
    capability: Capability
    endpoint: Any
    mapping: dict[str, Any]
    requests: tuple[PlannedRequest, ...]
    paging_supported: bool


def canonical_capabilities() -> tuple[tuple[str, Capability, str], ...]:
    """Return declared capability rows with endpoints sourced from mappings."""
    rows = []
    for capability in source_capabilities():
        mapping = get_mapping(capability.source, capability.dataset)
        rows.append((capability.dataset, capability, mapping["inspector"]["endpoint"]))
    return tuple(rows)


def _validate_selector(request: DatasetRequest) -> None:
    if request.dataset in {"symbol_list", "index_list"}:
        unsupported = [name for name in ("symbol", "index_code") if getattr(request, name)]
        if request.ascending is not None:
            unsupported.append("ascending")
        aliases = [(name, getattr(request, name)) for name in ("board", "market", "exchange")
                   if getattr(request, name)]
        if len({str(value).casefold() for _, value in aliases}) > 1:
            detail = ", ".join(f"--{name}={value}" for name, value in aliases)
            raise ParameterError(f"conflicting board aliases: {detail}")
        if request.dataset == "symbol_list" and not aliases:
            raise ParameterError("symbol-list requires --board (compatible --market/--exchange aliases are accepted)")
        if unsupported:
            flags = ", ".join(f"--{name.replace('_', '-')}" for name in unsupported)
            raise ParameterError(f"canonical dataset {request.dataset.replace('_', '-')} does not support: {flags}")
        return
    unsupported = [name for name in ("board", "market", "exchange") if getattr(request, name)]
    if request.ascending is not None:
        unsupported.append("ascending")
    if unsupported:
        flags = ", ".join(f"--{name.replace('_', '-')}" for name in unsupported)
        raise ParameterError(f"canonical dataset {request.dataset.replace('_', '-')} does not support: {flags}")
    if request.dataset == "index_daily":
        if not request.index_code or request.symbol:
            raise ParameterError("index-daily requires --index-code and does not accept --symbol")
    elif not request.symbol or request.index_code:
        raise ParameterError(f"{request.dataset.replace('_', '-')} requires --symbol and does not accept --index-code")


def _validate_dates(request: DatasetRequest) -> tuple[Any, Any]:
    if request.date and (request.from_date or request.to_date):
        raise ParameterError("--date cannot be used with --from-date/--to-date")
    if bool(request.from_date) != bool(request.to_date):
        raise ParameterError("--from-date and --to-date must be supplied together")
    if request.date:
        start = end = parse_date(request.date)
    elif request.from_date and request.to_date:
        start, end = parse_date(request.from_date), parse_date(request.to_date)
    else:
        raise ParameterError("A canonical dataset requires --date or both --from-date and --to-date")
    if start > end:
        raise ParameterError("--from-date must be earlier than or equal to --to-date")
    return start, end


def build_dataset_plan(
    request: DatasetRequest,
    requested_source: str | None,
    *,
    page_index_explicit: bool = False,
    page_size_explicit: bool = False,
) -> DatasetPlan:
    """Resolve source/mapping/endpoint and validate the complete plan before I/O."""
    _validate_selector(request)
    is_catalog = request.dataset in {"symbol_list", "index_list"}
    if is_catalog:
        supplied_dates = [name for name in ("date", "from_date", "to_date") if getattr(request, name)]
        if supplied_dates:
            flags = ", ".join(f"--{name.replace('_', '-')}" for name in supplied_dates)
            raise ParameterError(f"canonical catalog dataset does not support: {flags}")
        start = end = None
    else:
        start, end = _validate_dates(request)
    capability = resolve_source(request.dataset, requested_source, production=False)
    mapping = get_mapping(capability.source, request.dataset)
    endpoint_name = mapping.get("inspector", {}).get("endpoint")
    endpoints = registry(capability.source)
    if not endpoint_name or endpoint_name not in endpoints:
        raise ParameterError(
            f"{capability.source}/{request.dataset} mapping names unavailable inspector endpoint {endpoint_name!r}"
        )
    endpoint = endpoints[endpoint_name]
    if endpoint.native_name != endpoint_name:
        raise ParameterError(f"mapping endpoint {endpoint_name!r} is not a native endpoint")

    paging_supported = endpoint_name not in {"index-summary", "securities-by-board"} and not (
        capability.source == "ssi_v3" and endpoint_name == "index-list"
    )
    if not paging_supported and (page_index_explicit or page_size_explicit):
        raise ParameterError(f"{endpoint_name} does not support --page-index/--page-size")

    planned: list[PlannedRequest] = []
    if is_catalog:
        aliases = [getattr(request, name) for name in ("board", "market", "exchange")
                   if getattr(request, name)]
        normalized = replace(request, board=aliases[0] if aliases else None, market=None, exchange=None)
        planned.append(PlannedRequest(request, endpoint.build_params(normalized), "current response"))
    elif capability.source == "ssi_v3" and request.dataset == "index_daily":
        count = (end.date() - start.date()).days + 1
        if count > MAX_DATA_REQUESTS:
            raise ParameterError(
                f"request plan has {count} data requests; maximum is {MAX_DATA_REQUESTS}; narrow the date range"
            )
        current = start
        while current <= end:
            day = current.strftime("%Y-%m-%d")
            item = replace(request, date=day, from_date=None, to_date=None)
            planned.append(PlannedRequest(item, endpoint.build_params(item), day))
            current += timedelta(days=1)
    else:
        planned.append(PlannedRequest(request, endpoint.build_params(request),
                                      request.date or f"{request.from_date}..{request.to_date}"))
    if len(planned) > MAX_DATA_REQUESTS:
        raise ParameterError(f"request plan exceeds maximum {MAX_DATA_REQUESTS}")
    return DatasetPlan(requested_source, capability, endpoint, mapping, tuple(planned), paging_supported)
