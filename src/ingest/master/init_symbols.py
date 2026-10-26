"""Compatibility entrypoint for the guarded versioned master synchronizer."""
from .sync import run_master_sync
from src.providers.ssi.adapters.master_v3 import map_verified_record


def init_symbols(*, dataset=None, data_source=None, write=False):
    return run_master_sync(dataset, data_source=data_source, write=write)


def map_security_record(item: dict):
    return map_verified_record("securities", item)
