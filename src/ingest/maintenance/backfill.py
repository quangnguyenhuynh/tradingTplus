"""Guarded Intraday orchestration and legacy backfill import compatibility."""
from __future__ import annotations
from src.providers.ssi.capabilities import CapabilityUnavailableError

from typing import Any
from warnings import warn
from src.providers.ssi.registry import resolve_source

from src.ingest.stock_daily.daily import run_daily_ingest
# Compatibility re-exports: one canonical Stock runner and shared helper set.
from src.ingest.stock_daily.backfill import run_daily_backfill_pipeline, _run_ingest_backfill
from src.ingest.shared.backfill_range import (
    _BackfillRange, _resolve_range, _range_status, _failure_day, _base_range_summary,
)
from src.ingest.shared.date_utils import parse_ddmmyyyy, parse_iso_date, validate_not_future
from src.ingest.shared.pipeline_status import status_from_ingest as _status_from_ingest, validate_pipeline_summary as _validate_pipeline_summary
from src.quality.completeness.ingest_check import check_ingest
from src.ingest.stock_intraday.intraday_ingest import run_intraday_ingest
from src.ingest.stock_intraday.manual import run_manual_intraday, scope as manual_scope
from src.ingest.shared.symbol_scope import normalize_symbol_scope


def _intraday_plan(from_date, to_date, symbols, data_source):
    """Validate the complete work scope before any client, fetch or mutation."""
    start, end = parse_ddmmyyyy(from_date), parse_ddmmyyyy(to_date)
    validate_not_future(start)
    validate_not_future(end)
    if start.date > end.date:
        raise ValueError('from_date must be <= to_date')
    if not isinstance(symbols, (list, tuple)) or not symbols:
        raise ValueError('An explicit nonempty --symbols list is required')
    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError('Each requested symbol must be a concrete nonblank stock symbol')
    requested = normalize_symbol_scope(symbols)
    # Count weekdays arithmetically before enumerating a potentially huge range.
    calendar_days = (end.date - start.date).days + 1
    weeks, remainder = divmod(calendar_days, 7)
    weekdays = weeks * 5 + sum((start.date.weekday() + i) % 7 < 5 for i in range(remainder))
    if weekdays * len(requested) > 50:
        raise ValueError('Intraday backfill is limited to 50 symbol/weekday pairs; split the range')
    for symbol in requested:
        try:
            manual_scope(start.iso, [symbol], 'ssi_v3' if data_source is None else data_source)
        except OverflowError as exc:
            raise ValueError('Requested date cannot be normalized to a UTC trading-day scope') from exc
    return _resolve_range(from_date, to_date), requested


def run_intraday_backfill_pipeline(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None, data_source: str | None = None,
    *, write: bool = False,
) -> dict[str, Any]:
    """Sequential operator-only range of guarded manual pairs; dry-run by default."""
    if type(write) is not bool:
        raise ValueError('write must be an explicit boolean')
    date_range, requested = _intraday_plan(from_date, to_date, symbols, data_source)
    planned = len(date_range.eligible_dates) * len(requested)
    results = []
    halted = False
    for day in date_range.eligible_dates:
        for symbol in requested:
            try:
                # This call owns all fetch/map/eligibility/conflict/persistence
                # logic. No raw candles or clean working batches are retained here.
                pair = dict(run_manual_intraday(day, symbols=[symbol], data_source='ssi_v3', write=write))
                pair['pilot_status'] = pair.get('status')
                if (pair.get('raw_received') == 0 and pair.get('pagination_complete') is True and
                    pair.get('source_status') == 'EMPTY'):
                    pair.update(status='NO_SOURCE_DATA', error_category='NO_SOURCE_DATA', write_ready=False,
                                reason='Explicit empty source response; holiday/market coverage is unverified')
                elif pair.get('status') == 'OK' and (pair.get('db_preflight') != 'PASS' or not pair.get('write_ready')):
                    pair.update(status='BLOCKED', failed_stage='configuration', error_category='DB_PREFLIGHT_UNVERIFIED',
                                systemic_failure=True, write_ready=False,
                                reason='Source-only preview is not an approved DB write plan; configure DB and rerun')
                elif pair.get('status') not in {'OK', 'BLOCKED', 'PARTIAL', 'FAILED'}:
                    pair.update(status='FAILED', error_category='INVALID_PAIR_RESULT', systemic_failure=True,
                                reason='Manual pilot returned an unsupported result; stop safely')
                if pair.get('db_preflight') == 'NOT_RUN_NO_CREDENTIALS' and not pair.get('systemic_failure'):
                    pair.update(systemic_failure=True, error_category='DB_PREFLIGHT_UNVERIFIED', write_ready=False,
                                reason='DB preflight is unavailable; source evidence does not approve this range')
            except Exception as exc:
                # No uncertain retry and no exception body (may contain secrets).
                pair = dict(status='FAILED', write_ready=False, failed_stage='pair_invocation',
                            error_category='SHARED_DEPENDENCY', systemic_failure=True,
                            errors=[dict(type=type(exc).__name__, message='Pair invocation failed; inspect sanitized operator logs')],
                            recovery='Inspect completed scopes read-only, correct the dependency, then rerun the same explicit scope')
            pair.update(symbol=symbol, date=parse_ddmmyyyy(day).iso, mode='WRITE' if write else 'DRY_RUN',
                        data_source='ssi_v3', completeness_status='UNVERIFIED')
            for field in ('raw_received', 'mapped_valid', 'raw_inserted', 'clean_inserted',
                          'raw_skipped_existing', 'clean_skipped_existing', 'conflict_count'):
                pair.setdefault(field, 0)
            for field in ('failed_stage', 'error_category', 'planned_raw_insert', 'planned_clean_insert', 'recovery'):
                pair.setdefault(field, None)
            pair.setdefault('pagination_complete', False)
            pair.setdefault('validation_status', 'NOT_RUN')
            if pair.get('status') != 'OK':
                if not pair.get('recovery'):
                    pair['recovery'] = 'Inspect this symbol/day read-only, resolve the reported cause, then rerun; no overwrite/cleanup is performed'
            results.append(pair)
            if pair.get('systemic_failure'):
                halted = True
                break
        if halted:
            break
    counts = {status: sum(p['status'] == status for p in results)
              for status in ('OK', 'BLOCKED', 'PARTIAL', 'FAILED', 'NO_SOURCE_DATA')}
    status = ('OK' if planned == 0 or counts['OK'] == planned else
              'PARTIAL' if counts['OK'] else 'FAILED')
    errors = [dict(symbol=p['symbol'], date=p['date'], status=p['status'],
                   error_category=p.get('error_category'), failed_stage=p.get('failed_stage'),
                   reason=p.get('reason') or (p.get('failures') or ['Pair did not complete verified work'])[0])
              for p in results if p['status'] != 'OK']
    summary = dict(flow='backfill-intraday', mode='WRITE' if write else 'DRY_RUN', data_source='ssi_v3',
                   from_date=date_range.from_date, to_date=date_range.to_date,
                   requested_symbols=requested, symbols=requested, symbol_scope='EXPLICIT', symbol_count=len(requested),
                   requested_calendar_days=date_range.requested_calendar_days, eligible_days=len(date_range.eligible_dates),
                   eligible_dates=list(date_range.eligible_dates), skipped_weekend_dates=list(date_range.skipped_weekend_dates),
                   skipped_weekend_days=len(date_range.skipped_weekend_dates), planned_pairs=planned, processed_pairs=len(results),
                   unprocessed_pairs=planned - len(results), processed_days=len({p['date'] for p in results}),
                   ok_pairs=counts['OK'], blocked_pairs=counts['BLOCKED'], partial_pairs=counts['PARTIAL'],
                   failed_pairs=counts['FAILED'], no_source_data_pairs=counts['NO_SOURCE_DATA'],
                   halted=halted, halt_reason=results[-1].get('error_category') if halted else None,
                   per_symbol_date=results, errors=errors, error_count=len(errors), status=status,
                   completeness_status='UNVERIFIED',
                   write_ready=bool(planned and counts['OK'] == planned and all(p.get('write_ready') for p in results)),
                   insert_counts_confirmed=all(p.get('insert_counts_confirmed', True) for p in results))
    for field in ('raw_received', 'mapped_valid', 'rejected', 'duplicate_count', 'raw_inserted', 'clean_inserted',
                  'raw_skipped_existing', 'clean_skipped_existing', 'conflict_count'):
        summary[field] = sum(p.get(field, 0) or 0 for p in results)
    for field in ('planned_raw_insert', 'planned_clean_insert'):
        summary[field] = (sum(p[field] for p in results)
                          if len(results) == planned and all(p.get(field) is not None for p in results) else None)
    completed = {(p['date'], p['symbol']) for p in results}
    summary['unprocessed_symbol_date'] = [dict(date=parse_ddmmyyyy(day).iso, symbol=symbol, status='NOT_RUN',
                                               reason=summary['halt_reason'])
                                           for day in date_range.eligible_dates for symbol in requested
                                           if (parse_ddmmyyyy(day).iso, symbol) not in completed]
    return summary


def _branch_ingest(day_summary: dict[str, Any] | None, key: str) -> dict[str, Any]:
    if not day_summary:
        return {"status": "FAILED", "symbol_count": 0, "error_count": 1, "errors": ["missing branch day summary"]}
    value = day_summary.get(key)
    if isinstance(value, dict):
        return value
    return {
        "status": "FAILED",
        "symbol_count": 0,
        "error_count": 1,
        "errors": [day_summary.get("error") or f"missing {key}"],
    }


def run_backfill_pipeline(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None, data_source: str | None = None,
) -> dict[str, Any]:
    raise CapabilityUnavailableError("stock_intraday")


def backfill(
    from_date: str,
    to_date: str,
    symbols: list[str] | tuple[str, ...] | None = None,
    allow_future: bool = False,
) -> dict[str, Any]:
    """Deprecated compatibility wrapper; use :func:`run_backfill_pipeline`."""
    warn("backfill() is deprecated; use run_backfill_pipeline()", DeprecationWarning, stacklevel=2)
    if allow_future:
        raise ValueError("future-date backfill is unsupported")

    def normalize(value: str) -> str:
        try:
            return parse_ddmmyyyy(value).ddmmyyyy
        except ValueError:
            return parse_iso_date(value).ddmmyyyy

    return run_backfill_pipeline(normalize(from_date), normalize(to_date), symbols=symbols)


__all__ = [
    "backfill",
    "run_daily_backfill_pipeline",
    "run_intraday_backfill_pipeline",
    "run_backfill_pipeline",
]
