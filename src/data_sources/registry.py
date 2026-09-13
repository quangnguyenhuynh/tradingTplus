"""Per-dataset readiness registry for production and inspector selection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .ssi_v2 import SSIV2Adapter

PRODUCTION_DATASETS = ("stock_daily", "stock_intraday", "index_daily")
INSPECTOR_ONLY_DATASETS = ("symbol_list", "index_list")
DATASETS = PRODUCTION_DATASETS + INSPECTOR_ONLY_DATASETS


class DataSourceError(ValueError): pass
class UnsupportedDatasetError(DataSourceError): pass
class SourceNotReadyError(DataSourceError): pass


@dataclass(frozen=True)
class Capability:
    source: str
    dataset: str
    order: int
    status: str
    factory: Callable[[], object] | None
    note: str = ""


_CAPABILITIES = tuple(
    [Capability("ssi_v2", dataset, 2, "ready", SSIV2Adapter) for dataset in PRODUCTION_DATASETS]
    + [Capability("ssi_v3", dataset, 3, "preview", None,
                  "Response semantics and clean mapping are not fully verified; inspector only")
       for dataset in PRODUCTION_DATASETS]
    + [Capability(source, dataset, order, "preview", None,
                  "Catalog preview for API inspection only; not a production sync capability")
       for source, order in (("ssi_v2", 2), ("ssi_v3", 3))
       for dataset in INSPECTOR_ONLY_DATASETS]
)


def source_capabilities() -> tuple[Capability, ...]:
    return _CAPABILITIES


def resolve_source(dataset: str, requested: str | None = None, *, production: bool = True) -> Capability:
    if dataset not in DATASETS:
        raise UnsupportedDatasetError(f"unknown dataset: {dataset}")
    candidates = [item for item in _CAPABILITIES if item.dataset == dataset]
    if requested is not None:
        matches = [item for item in candidates if item.source == requested]
        if not matches:
            known = {item.source for item in _CAPABILITIES}
            if requested in known:
                raise UnsupportedDatasetError(f"data source {requested} does not support dataset {dataset}")
            raise DataSourceError(f"unknown data source: {requested}")
        selected = matches[0]
    else:
        eligible = [item for item in candidates if not production or item.status == "ready"]
        if not eligible:
            raise SourceNotReadyError(f"no production-ready data source supports dataset {dataset}")
        selected = max(eligible, key=lambda item: item.order)
    if production and selected.status != "ready":
        raise SourceNotReadyError(
            f"data source {selected.source} is {selected.status}, not ready for dataset {dataset}"
        )
    return selected


def create_production_adapter(dataset: str, requested: str | None = None):
    capability = resolve_source(dataset, requested, production=True)
    if capability.factory is None:  # defensive: readiness and implementation are separate checks
        raise SourceNotReadyError(f"data source {capability.source} has no production adapter for {dataset}")
    return capability, capability.factory()
