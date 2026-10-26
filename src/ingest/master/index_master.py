"""Compatibility imports; no retired SSI v2 fetching or mapping logic."""
from .sync import run_master_sync
from src.providers.ssi.adapters.master_v3 import map_verified_record


def sync_index_master(ssi=None, db=None, *, data_source=None, write=False):
    if ssi is not None or db is not None:
        raise ValueError("Legacy SSI/DB injection is unsupported; use the master provider/store contract")
    return run_master_sync("index_master", data_source=data_source, write=write)


def sync_index_components(index_codes=None, ssi=None, db=None, *, data_source=None, write=False):
    if index_codes is not None or ssi is not None or db is not None:
        raise ValueError("Scoped index membership is unverified; legacy source injection is unsupported")
    return run_master_sync("index_components", data_source=data_source, write=write)


def map_index_master_record(item):
    return map_verified_record("index_master", item)


def map_index_component_record(item, requested_code):
    return map_verified_record("index_components", item)


sync_indexes = sync_index_master
map_index_record = map_index_master_record
