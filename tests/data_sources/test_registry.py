import pytest

from src.data_sources.registry import SourceNotReadyError, resolve_source


@pytest.mark.parametrize("dataset", ["stock_daily", "stock_intraday", "index_daily"])
def test_production_selects_latest_ready_per_dataset(dataset):
    assert resolve_source(dataset).source == "ssi_v2"


@pytest.mark.parametrize("dataset", ["stock_daily", "stock_intraday", "index_daily"])
def test_inspector_selects_latest_registered_preview(dataset):
    selected = resolve_source(dataset, production=False)
    assert (selected.source, selected.status) == ("ssi_v3", "preview")


def test_explicit_ready_source_is_honoured():
    assert resolve_source("stock_daily", "ssi_v2").source == "ssi_v2"


def test_preview_source_is_rejected_for_production_before_api_use():
    with pytest.raises(SourceNotReadyError, match="ssi_v3.*stock_daily"):
        resolve_source("stock_daily", "ssi_v3")
