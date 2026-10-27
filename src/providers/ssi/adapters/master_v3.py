"""Verified SSI v3 security catalog; index capabilities remain blocked."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from src.config import config
from src.providers.ssi.clients.rest_v3 import SSIV3Client, SSIReadError
from src.providers.ssi.master_contract import MASTER_DATASETS, MasterSourceError, MasterSnapshot

BOARDS = ('HOSE', 'HNX', 'UPCOM')
MAPPING_VERSION = 'ssi_v3.unified_symbols.2.0.0'
# Historical anomaly reference, NOT expected totals or an authoritative universe.
OWNER_REFERENCE = {'date': '2026-10-26/27', 'counts': {'HOSE': 793, 'HNX': 410, 'UPCOM': 851}}
KNOWN_TYPES = frozenset(('Stock', 'Bond', 'ETF Product', 'Investment Fund'))
VERIFIED_FIELDS = frozenset(('symbol', 'symbolNameVi', 'symbolNameEn', 'board', 'stockType',
    'lotSize', 'listedShare', 'firstTradingDate', 'lastTradingDate', 'maturityDate',
    'cwUnderlyingSymbol', 'cwExercisePrice', 'cwExecutionRatio', 'icbCode', 'icbName',
    'iIndex', 'iNav', 'openInterest', 'settlementPrice'))
NUMERIC_FIELDS = ('lotSize', 'listedShare')
DATE_FIELDS = ('firstTradingDate', 'lastTradingDate', 'maturityDate')


def _text(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise MasterSourceError('INVALID_SOURCE_TEXT')
    if any(secret and str(secret) in value for secret in (config.SSI_API_KEY, config.SSI_API_SECRET)):
        raise MasterSourceError('SOURCE_SECRET_IN_RECORD')
    return value.strip()


def _numeric(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise MasterSourceError('INVALID_SOURCE_NUMERIC')
    if isinstance(value, str) and not re.fullmatch(r'[+]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?', value.strip()):
        raise MasterSourceError('INVALID_SOURCE_NUMERIC')
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise MasterSourceError('INVALID_SOURCE_NUMERIC') from None
    if not number.is_finite() or number < 0:
        raise MasterSourceError('INVALID_SOURCE_NUMERIC')
    return str(number)


def _date(value):
    value = _text(value)
    if value is None:
        return None
    if not re.fullmatch(r'\d{4}([/-])\d{2}\1\d{2}', value):
        raise MasterSourceError('INVALID_SOURCE_DATE')
    try:
        return datetime.strptime(value.replace('/', '-'), '%Y-%m-%d').date().isoformat()
    except ValueError:
        raise MasterSourceError('INVALID_SOURCE_DATE') from None


def _safe_raw(value, sensitive_values=()):
    """Drop secret-bearing keys recursively; preserve JSON-safe exact decimals."""
    if isinstance(value, dict):
        return {k: _safe_raw(v, sensitive_values) for k, v in value.items()
                if not any(marker in str(k).replace('_', '').casefold()
                           for marker in ('token', 'secret', 'password', 'authorization', 'apikey', 'consumerid'))}
    if isinstance(value, list):
        return [_safe_raw(v, sensitive_values) for v in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise MasterSourceError('INVALID_SOURCE_JSON')
        return int(value) if value == value.to_integral_value() else str(value)
    if isinstance(value, str):
        for secret in (config.SSI_API_KEY, config.SSI_API_SECRET, *sensitive_values):
            if secret:
                value = value.replace(str(secret), '[REDACTED]')
        return value
    if value is None or isinstance(value, (bool, int)):
        return value
    # JSON decoder used for this endpoint never produces binary floats.
    raise MasterSourceError('INVALID_SOURCE_JSON')


def map_verified_record(dataset: str, payload: dict, *, requested_board: str | None = None,
                        sensitive_values=()):
    """One source validation/mapping implementation for both master datasets."""
    if dataset not in MASTER_DATASETS:
        raise ValueError('Unknown master dataset')
    if dataset not in ('symbols', 'securities'):
        raise MasterSourceError('SSI_V3_MASTER_MAPPING_UNVERIFIED')
    if not isinstance(payload, dict):
        raise MasterSourceError('INVALID_SOURCE_RECORD')
    for field in ('symbol', 'board', 'symbolNameVi', 'symbolNameEn', 'stockType'):
        value = payload.get(field)
        if isinstance(value, str) and any(secret and str(secret) in value for secret in sensitive_values):
            raise MasterSourceError('SOURCE_SECRET_IN_RECORD')
    symbol = _text(payload.get('symbol'))
    if symbol is None or not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,63}', symbol.upper()):
        raise MasterSourceError('INVALID_SOURCE_IDENTITY')
    board = _text(payload.get('board'))
    derivative = requested_board == 'HNX' and board == 'DERIVATIVES' and payload.get('stockType') == 'Future'
    if not derivative and (board not in BOARDS or (requested_board is not None and board != requested_board)):
        raise MasterSourceError('SOURCE_BOARD_MISMATCH')
    vi, en, kind = (_text(payload.get(k)) for k in ('symbolNameVi', 'symbolNameEn', 'stockType'))
    numbers = {k: _numeric(payload.get(k)) for k in NUMERIC_FIELDS}
    dates = {k: _date(payload.get(k)) for k in DATE_FIELDS}
    # Extra verified fields stay raw-only, unknown fields are retained only after
    # recursive credential redaction and strict JSON-safe validation.
    raw = _safe_raw(payload, sensitive_values)
    return {'symbol': symbol.upper(), 'name': vi, 'stock_en_name': en,
            'market': board, 'exchange': board, 'sec_type': kind,
            'lot_size': numbers['lotSize'], 'listed_share': numbers['listedShare'],
            'first_trading_date': dates['firstTradingDate'], 'last_trading_date': dates['lastTradingDate'],
            'maturity_date': dates['maturityDate'], 'raw': raw}


class SSIV3MasterAdapter:
    source_id = 'ssi_v3'
    mapping_version = MAPPING_VERSION
    candidates = {
        'symbols': ('/data/securitiesByBoard',), 'securities': ('/data/securitiesByBoard',),
        'index_master': ('/data/indexList',), 'index_components': ('/data/securitiesByBoard',),
    }

    def __init__(self, client=None, *, reference=None):
        # reference injection supports small offline samples, not a public CLI
        # bypass. Production uses the owner evidence until separately reviewed.
        self.client = client
        self.reference = OWNER_REFERENCE if reference is None else reference

    def fetch(self, dataset: str) -> MasterSnapshot:
        if dataset not in MASTER_DATASETS:
            raise ValueError('Unknown master dataset')
        if dataset not in ('symbols', 'securities'):
            raise MasterSourceError('SSI_V3_MASTER_RESPONSE_UNVERIFIED')
        client = self.client if self.client is not None else SSIV3Client()
        records, errors, diagnostics, seen, excluded = [], [], [], set(), []
        received = 0
        for board in BOARDS:
            diagnostic = {'board': board, 'status': 'NOT_RUN', 'records_received': None,
                          'records_mapped': 0, 'excluded_records': 0, 'actual_markets': {}, 'security_types': {}, 'unknown_security_types': {}}
            diagnostics.append(diagnostic)
            try:
                rows = client.securities_by_board(board)
                if not isinstance(rows, list):
                    raise MasterSourceError('SSI_INVALID_ENVELOPE')
                diagnostic.update(status='PASS', records_received=len(rows), http_body_received=True,
                                  response_parsing='PASS', pagination='NOT_APPLICABLE')
                received += len(rows)
                if not rows:
                    raise MasterSourceError('SOURCE_BOARD_EMPTY')
                if len(rows) > 20_000:
                    raise MasterSourceError('SOURCE_BOARD_LIMIT')
                types, unknown = Counter(), Counter()
                for position, row in enumerate(rows, 1):
                    try:
                        if (board == 'HOSE' and isinstance(row, dict) and row.get('symbol') == 'VN50 GROWTH'
                                and row.get('board') == 'HOSE' and row.get('stockType') is None):
                            if 'VN50 GROWTH' in seen:
                                raise MasterSourceError('DUPLICATE_SOURCE_IDENTITY')
                            seen.add('VN50 GROWTH')
                            excluded.append({'symbol': 'VN50 GROWTH', 'requested_board': board,
                                             'reason': 'OWNER_VERIFIED_INDEX_LIST_IDENTITY_OUTSIDE_SECURITY_SCOPE'})
                            diagnostic['excluded_records'] += 1
                            continue
                        mapped = map_verified_record(dataset, row, requested_board=board,
                                                     sensitive_values=(getattr(client, 'token', None),))
                        symbol = mapped['symbol']
                        if symbol in seen:
                            raise MasterSourceError('DUPLICATE_SOURCE_IDENTITY')
                        seen.add(symbol)
                        records.append(mapped)
                        markets = diagnostic['actual_markets']
                        markets[mapped['market']] = markets.get(mapped['market'], 0) + 1
                        diagnostic['records_mapped'] += 1
                        kind = _text(row.get('stockType'))
                        types[kind if kind is not None else '<NULL>'] += 1
                        if kind not in KNOWN_TYPES:
                            unknown[kind if kind is not None else '<NULL>'] += 1
                    except MasterSourceError as exc:
                        errors.append({'code': exc.code, 'board': board, 'record': position})
                        diagnostic['status'] = 'FAILED'
                diagnostic['security_types'] = dict(types)
                diagnostic['unknown_security_types'] = dict(unknown)
                reference = self.reference.get('counts', {}).get(board)
                diagnostic['historical_reference_count'] = reference
                if reference is not None:
                    diagnostic['change_from_reference'] = len(rows) - reference
                    # A >50% decline is unexplained until evidence is refreshed.
                    # No equality to historical counts or universal floor assumed.
                    if len(rows) * 2 < reference:
                        raise MasterSourceError('SOURCE_COUNT_REGRESSION')
            except (SSIReadError, MasterSourceError) as exc:
                diagnostic['status'] = 'FAILED'
                code = getattr(exc, 'code', None)
                if code is None:
                    # Shared login errors predate structured codes. Never return
                    # their response text; distinguish configuration/auth safely.
                    code = 'SSI_AUTH_OR_CONFIGURATION' if getattr(client, 'token', None) is None else 'SSI_SOURCE_ERROR'
                errors.append({'code': code, 'board': board})
            # An independent board failure does not erase evidence from others;
            # there is still no partial write even if later boards succeed.
        complete = len(diagnostics) == 3 and all(d['status'] == 'PASS' for d in diagnostics) and not errors
        return MasterSnapshot(dataset, records, received, complete, {'kind': 'ALL'}, self.mapping_version,
            pagination={'mode': 'UNPAGINATED_ARRAY', 'boards': diagnostics,
                        'boards_enumerated': list(BOARDS), 'board_enumeration_complete': complete,
                        'provider_reported_total': None, 'authoritative_market_completeness': 'UNVERIFIED',
                        'historical_reference': self.reference,
                        'limitation': 'Parsed complete HTTP arrays from all three boards; no authoritative provider total.'},
            errors=errors, excluded_records=excluded, unsupported_fields=(
                ('issuer', 'issue_date', *(f'tick_{kind}{n}' for n in range(1,5) for kind in ('price','increment')))
                if dataset in ('symbols', 'securities') else ()),
            retention_policy={'group_field': 'market', 'minimum_fraction': '0.5',
                              'distribution_field': 'sec_type'})
