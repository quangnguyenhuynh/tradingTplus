"""SSI v3 1m preview adapter. No database access or production promotion."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from collections import Counter
from typing import Any

from src.contracts.intraday_preview import map_intraday_preview
from src.contracts.registry import get_mapping
from src.providers.ssi.base import AdapterResult
from src.providers.ssi.clients.rest_v3 import SSIV3Client, IntradayReadError
from src.quality.validators.intraday_validator import validate_intraday_batch


def preview_intraday(client: SSIV3Client, symbol: str, start: str, end: str | None = None,
                     *, page_index=1, page_size=None, max_pages=100, ascending=None) -> AdapterResult:
    try:
        result = client.ohlc_1m(symbol, start, end, page_index=page_index, page_size=page_size,
                                max_pages=max_pages, ascending=ascending)
    except IntradayReadError as exc:
        result = exc.result
    clean, reports = map_intraday_preview(result.items, symbol, start, end or start, source='ssi_v3')
    valid = [row for row in clean if row is not None]
    validation = validate_intraday_batch(valid)
    timestamps = [row['time'] for row in valid]
    instants = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in timestamps]
    received_order = ('descending' if len(instants) > 1 and all(b <= a for a, b in zip(instants, instants[1:])) else
                      'ascending' if len(instants) > 1 and all(b >= a for a, b in zip(instants, instants[1:])) else
                      'mixed' if len(instants) > 1 else 'single_or_empty')
    duplicates = sum(count - 1 for count in Counter(timestamps).values())
    ordering = sum(later < earlier for earlier, later in zip(instants, instants[1:]))
    errors = [error for report in reports for error in report['errors']]
    source_times = [next((v for k, v in row.items() if str(k).casefold() == 'tradingdate'),
                         next((v for k, v in row.items() if str(k).casefold() == 'time'), None))
                    if isinstance(row, dict) else None for row in result.items]
    raw_mapped = sum(row is not None for row in clean)
    status = ('FAILED' if not result.complete else 'EMPTY' if not result.items else
              'PARTIAL' if errors or validation.errors else 'PROVISIONAL')
    mapping = get_mapping('ssi_v3', 'stock_intraday')
    report: dict[str, Any] = {
        'source': 'ssi_v3', 'dataset': 'stock_intraday', 'status': status,
        'requested_symbol': symbol.upper(), 'from_date': start, 'to_date': end or start,
        'endpoint': '/api/v3/data/ohlc', 'timeframe': '1m',
        'contract_version': mapping['contract_version'], 'mapping_version': mapping['mapping_version'],
        'evidence': mapping['evidence'], 'production_ready': False,
        'records_received': len(result.items), 'records_mapped': raw_mapped, 'records_valid': raw_mapped,
        'records_rejected': len(result.items) - raw_mapped, 'record_reports': reports,
        'raw_pages': result.raw_pages, 'requests': result.request_params,
        'pages_requested': result.pages, 'pages_received': len(result.raw_pages),
        'pagination_complete': result.complete, 'pagination_termination': result.termination,
        'pagination_diagnostics': result.diagnostics,
        'pagination_scope': 'whole_range_from_page_1' if page_index == 1 else 'suffix_from_requested_page',
        'source_first_received_time': source_times[0] if source_times else None,
        'source_last_received_time': source_times[-1] if source_times else None,
        'canonical_first_received_utc': timestamps[0] if timestamps else None,
        'canonical_last_received_utc': timestamps[-1] if timestamps else None,
        'canonical_min_utc': min(instants).isoformat().replace('+00:00', 'Z') if instants else None,
        'canonical_max_utc': max(instants).isoformat().replace('+00:00', 'Z') if instants else None,
        'duplicate_timestamp_count': duplicates, 'ordering_anomalies': ordering,
        'received_order': received_order,
        'ordering_reference': 'Inversions are measured against ascending time; descending provider order is preserved, not repaired',
        'identity_error_count': sum(e.get('code') == 'IDENTITY_MISMATCH' for e in errors),
        'timestamp_error_count': sum(e.get('field') == 'time' for e in errors),
        'missing_optional_fields': sorted({f for r in reports for f in r.get('missing_optional', [])}),
        'unsupported_fields': {k: v['reason'] for k, v in mapping['fields'].items() if v.get('unsupported')},
        'validation_status': 'FAILED' if errors or validation.errors else 'PASS' if valid else 'NO_DATA',
        'validation_errors': [asdict(issue) for issue in validation.errors],
        'structural_warnings': [asdict(issue) for issue in validation.warnings],
        'completeness_status': 'UNVERIFIED',
        'completeness_reason': 'No verified calendar/bar convention; gaps may represent no trades. Never infer complete sessions from HTTP or row counts.',
        'timestamp_source_field': 'ohlc.tradingDate (verified); legacy ohlc.time explicit-offset compatibility',
        'timestamp_interpretation': 'Observed slash datetime: Asia/Ho_Chi_Minh market-local; explicit timezone timestamps retain their instant',
        'bar_timestamp_convention': 'UNVERIFIED',
        'value_source': 'ohlc.value',
        'value_interpretation': 'SSI-reported intraday candle value; preserved without estimation or fallback',
        'source_value_present_count': sum(r.get('source_value_present', False) for r in reports),
        'source_value_missing_count': sum(r.get('source_value_status') == 'MISSING' for r in reports),
        'source_value_invalid_count': sum(r.get('source_value_status') == 'INVALID' for r in reports),
        'source_value_mapped_count': sum(r.get('source_value_status') == 'MAPPED' for r in reports),
        'source_value_numeric_valid_count': sum(r.get('source_value_status') in ('MAPPED', 'VALIDATED_NOT_MAPPED') for r in reports),
        'source_value_semantics_verified': False,
        'errors': errors,
    }
    return AdapterResult('ssi_v3', 'stock_intraday', result.items, clean, errors, report,
                         raw_source='ssi_v3')
