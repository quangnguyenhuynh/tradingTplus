"""The removed provider must not remain importable as a runtime fallback."""
from pathlib import Path
import pytest
from src.providers.ssi.registry import DataSourceError, resolve_source


def test_v2_runtime_and_mapping_are_removed():
    for name in ("src/ssi/api.py", "src/ssi/streaming.py", "src/data_sources/ssi_v2.py", "src/contracts/mappings/ssi_v2.json"):
        assert not Path(name).exists()
    with pytest.raises(DataSourceError, match="unsupported data source"):
        resolve_source("stock_daily", "ssi_v2")
