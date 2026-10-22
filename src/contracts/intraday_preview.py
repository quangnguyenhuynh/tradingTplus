"""Shared, pure provisional 1m mapping; no endpoint, HTTP or persistence logic."""
from __future__ import annotations

from typing import Any
from datetime import datetime
from src.contracts.registry import get_mapping
from src.contracts.transforms import VN_TZ

from src.contracts import map_record
from src.contracts.transforms import to_date, to_symbol
from src.quality.validators.intraday_validator import validate_intraday_record
from dataclasses import asdict


def map_intraday_preview(rows: list[Any], symbol: str, start: str, end: str, *, source: str):
    """Preserve row alignment and reject invalid identity/OHLCV instead of repairing.

    Supported source names are the already-declared provisional dictionary.
    Explicit source identities/dates, if supplied, must agree with the request
    and with the candle's own timestamp. Unsupported source forms stay raw.
    """
    expected = to_symbol(symbol, {})
    start, end = to_date(start, {}), to_date(end, {})
    prefix = get_mapping(source, 'stock_intraday')['inspector'].get('prefix')
    clean, reports = [], []
    for number, row in enumerate(rows, 1):
        report = {'record': number, 'errors': [], 'missing_optional': []}
        candidate = None
        if not isinstance(row, dict):
            report['errors'].append({'code': 'INVALID_RECORD', 'message': 'expected candle object'})
        else:
            context = {'symbol': expected, 'from_date': start, 'to_date': end}
            record = {f'{prefix}.{key}': value for key, value in row.items()} if prefix else row
            mapped = map_record(source, 'stock_intraday', record, context)
            report.update(mapped.report)
            candidate = mapped.candidate
            # Do not silently select among conflicting differently-cased identities.
            for key, value in row.items():
                name = str(key).casefold()
                if name == 'timeframe' and value != '1m':
                    report['errors'].append({'code': 'SOURCE_TIMEFRAME_MISMATCH', 'field': str(key)})
                try:
                    if name == 'symbol' and to_symbol(value, {}) != expected:
                        raise ValueError('source symbol differs from requested symbol')
                    if name in ('date', 'tradingdate'):
                        # A full tradingDate datetime is itself the time source;
                        # validate its Vietnam instant via the source transform,
                        # not by truncating a UTC/offset timestamp to its written date.
                        if name == 'tradingdate' and isinstance(value, str) and len(value.strip()) > 10:
                            continue
                        source_date = to_date(value, {})
                        if source_date < start or source_date > end:
                            raise ValueError('source date is outside requested range')
                        if candidate:
                            timestamp = datetime.fromisoformat(candidate['time'].replace('Z', '+00:00'))
                            if timestamp.astimezone(VN_TZ).date().isoformat() != source_date:
                                raise ValueError('source date disagrees with candle timestamp')
                except (TypeError, ValueError) as exc:
                    report['errors'].append({'code': 'IDENTITY_MISMATCH', 'field': str(key), 'message': str(exc)})
            if candidate is not None:
                validation = validate_intraday_record(candidate)
                report['errors'].extend(asdict(issue) for issue in validation.errors)
                report['validation_warnings'] = [asdict(issue) for issue in validation.warnings]
        if isinstance(row, dict):
            source_values = [v for k, v in row.items() if str(k).casefold() == 'value']
            present = any(v is not None and v != '' for v in source_values)
            invalid = any(e.get('field') == 'value' for e in report['errors'])
            report['source_value_present'] = present
            report['source_value_status'] = ('INVALID' if invalid else 'MISSING' if not present else
                                             'MAPPED' if candidate and not report['errors'] else 'VALIDATED_NOT_MAPPED')
            if not present:
                report.setdefault('warnings', []).append({
                    'code': 'SOURCE_VALUE_MISSING', 'field': 'value',
                    'message': 'SSI source value absent/null/empty; canonical value stays NULL; no fallback',
                })
        if report['errors']:
            candidate = None
        report['records_valid'] = int(candidate is not None)
        report['records_rejected'] = int(candidate is None)
        clean.append(candidate)
        reports.append(report)
    return clean, reports
