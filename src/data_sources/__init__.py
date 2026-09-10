"""Dataset-specific market-data source adapters and capability selection."""

from .registry import (
    DataSourceError,
    SourceNotReadyError,
    UnsupportedDatasetError,
    create_production_adapter,
    resolve_source,
    source_capabilities,
)

__all__ = [
    "DataSourceError", "SourceNotReadyError", "UnsupportedDatasetError",
    "create_production_adapter", "resolve_source", "source_capabilities",
]
