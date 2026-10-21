import pytest

from src.providers.ssi.registry import (DataSourceError, SourceNotReadyError, create_production_adapter,
                                       resolve_source)


def test_production_selects_latest_ready_per_dataset():
    assert resolve_source("stock_daily").source == "ssi_v3"
    with pytest.raises(SourceNotReadyError):
        resolve_source("stock_intraday")


@pytest.mark.parametrize("dataset", ["stock_daily", "stock_intraday"])
def test_inspector_selects_latest_registered_preview(dataset):
    selected = resolve_source(dataset, production=False)
    expected_status = "ready" if dataset == "stock_daily" else "preview"
    assert (selected.source, selected.status) == ("ssi_v3", expected_status)


def test_explicit_v3_is_ready_and_v2_is_unsupported():
    assert resolve_source("stock_daily", "ssi_v3").status == "ready"
    with pytest.raises(DataSourceError, match="unsupported data source"):
        resolve_source("stock_daily", "ssi_v2")


def test_index_daily_defaults_to_v3_and_rejects_v2_for_production():
    assert (resolve_source("index_daily").source, resolve_source("index_daily").status) == ("ssi_v3", "ready")
    with pytest.raises(DataSourceError, match="unsupported data source"):
        resolve_source("index_daily", "ssi_v2")


def test_preview_intraday_source_is_rejected_for_production_before_api_use():
    with pytest.raises(SourceNotReadyError, match="ssi_v3.*stock_intraday"):
        resolve_source("stock_intraday", "ssi_v3")


@pytest.mark.parametrize("dataset", ["symbol_list", "index_list"])
def test_catalog_datasets_are_v3_inspector_only(dataset):
    assert resolve_source(dataset, production=False).source == "ssi_v3"
    with pytest.raises(DataSourceError):
        resolve_source(dataset, "ssi_v2", production=False)
    with pytest.raises(SourceNotReadyError):
        create_production_adapter(dataset)
