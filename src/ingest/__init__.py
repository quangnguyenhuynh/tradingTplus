"""Ingestion public interfaces; domains are loaded only when explicitly requested."""
from importlib import import_module

_EXPORTS = {'init_symbols': ('src.ingest.master.init_symbols', 'init_symbols'), 'fetch_one_day': ('src.diagnostics.fetch_one_day', 'fetch_one_day'), 'fetch_one_day_with_clients': ('src.diagnostics.fetch_one_day', 'fetch_one_day_with_clients'), 'backfill': ('src.ingest.maintenance.backfill', 'backfill'), 'run_backfill_pipeline': ('src.ingest.maintenance.backfill', 'run_backfill_pipeline'), 'run_daily_backfill_pipeline': ('src.ingest.maintenance.backfill', 'run_daily_backfill_pipeline'), 'run_intraday_backfill_pipeline': ('src.ingest.maintenance.backfill', 'run_intraday_backfill_pipeline'), 'daily_run': ('src.ingest.stock_daily.daily', 'daily_run'), 'run_daily_ingest': ('src.ingest.stock_daily.daily', 'run_daily_ingest'), 'run_stock_eod_pipeline': ('src.ingest.workflows.stock_eod', 'run_stock_eod_pipeline'), 'run_stock_intraday_pipeline': ('src.ingest.workflows.stock_intraday', 'run_stock_intraday_pipeline'), 'run_intraday_ingest': ('src.ingest.stock_intraday.intraday_ingest', 'run_intraday_ingest'), 'run_refill_pipeline': ('src.ingest.maintenance.refill', 'run_refill_pipeline'), 'run_index_daily_ingest': ('src.ingest.index_daily.index_daily', 'run_index_daily_ingest'), 'run_index_backfill_pipeline': ('src.ingest.index_daily.index_backfill', 'run_index_backfill_pipeline'), 'check_index_completeness': ('src.quality.completeness.index_completeness', 'check_index_completeness'), 'run_streaming_ingest': ('src.ingest.streaming.streaming_snapshot', 'run_streaming_ingest')}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
