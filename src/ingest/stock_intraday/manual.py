"""Guarded single-symbol/day pilot. Does not enable generic intraday ingestion.

All validation/preflight precedes mutations. Insert-on-conflict DO NOTHING plus
readback prevents overwriting concurrent/historical rows. Separate raw/clean
requests are deliberately not described as a cross-table transaction.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from zoneinfo import ZoneInfo

from src.config import config
from src.database.client import SupabaseClient
from src.providers.ssi.adapters.v3 import SSIV3Adapter
from src.providers.ssi.registry import resolve_source

VN = ZoneInfo('Asia/Ho_Chi_Minh')
CANONICAL = ('symbol', 'timeframe', 'time', 'open', 'high', 'low', 'close', 'volume', 'value')
RAW_FIELDS = ('symbol', 'time', 'open', 'high', 'low', 'close', 'volume', 'data_hash', 'payload', 'source')


class PilotBlocked(ValueError):
    pass


def scope(date: str | None, symbols, data_source: str | None = None):
    """Reject broad/implicit scope before constructing any external client."""
    if not isinstance(date, str) or not re.fullmatch(r'(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', date):
        raise ValueError('Exactly one explicit date is required: DD/MM/YYYY or YYYY-MM-DD')
    day = datetime.strptime(date, '%d/%m/%Y' if '/' in date else '%Y-%m-%d').date()
    if day > datetime.now(VN).date():
        raise ValueError('Future trading dates are not allowed')
    if not isinstance(symbols, (list, tuple)) or len(symbols) != 1:
        raise ValueError('Exactly one explicit --symbols stock symbol is required')
    symbol = str(symbols[0]).strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,19}', symbol) or symbol == 'ALL':
        raise ValueError('A single concrete stock symbol is required; no ALL, wildcard or comma scopes')
    capability = resolve_source('stock_intraday', data_source, production=False)
    if capability.source != 'ssi_v3':
        raise ValueError('The manual pilot supports ssi_v3 only')
    start = datetime.combine(day, datetime.min.time(), VN).astimezone(timezone.utc)
    return day.isoformat(), symbol, start, start + timedelta(days=1)


def instant(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise PilotBlocked('Database/source timestamp must be timezone-aware')
    return parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def semantic_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _failure_category(stage, exc, diagnostics):
    """Add orchestration metadata only; do not change pilot status/write policy."""
    if isinstance(exc, PilotBlocked) and str(exc) == 'Database returned an error':
        return 'DB_DEPENDENCY', True
    if stage == 'configuration':
        return 'CONFIGURATION', True
    messages = [str(d.get('message', '')) for d in diagnostics
                if isinstance(d, dict) and d.get('code') == 'REQUEST_FAILED']
    if any(('Missing SSI_API_KEY/SSI_API_SECRET' in m or '/auth/token' in m or
            'authentication response omitted access token' in m or
            re.search(r'(?:http_status|api_code)=[\'\"]?(?:401|403)\b', m)) for m in messages):
        return 'SSI_AUTH_CONFIGURATION', True
    if any(('network failure for ' in m or re.search(r'(?:http_status|api_code)=[\'\"]?(?:429|5\d\d)\b', m)) for m in messages):
        return 'SSI_SHARED_DEPENDENCY', True
    if stage == 'source_fetch_validation':
        if not isinstance(exc, PilotBlocked) and not diagnostics:
            return 'SSI_SHARED_DEPENDENCY', True
        return ('SOURCE_UNAVAILABLE' if any(d.get('code') == 'REQUEST_FAILED' for d in diagnostics)
                else 'SOURCE_VALIDATION'), False
    if stage in {'eligibility', 'clean_preflight_recheck'} and isinstance(exc, PilotBlocked) and (
        str(exc).startswith('Symbol eligibility blocked:') or str(exc).startswith('Requested symbol is missing')):
        return 'SYMBOL_INELIGIBLE', False
    if not isinstance(exc, PilotBlocked):
        return 'DB_DEPENDENCY', True
    return 'CONFLICT_OR_PREFLIGHT' if stage in {'conflict_preflight', 'clean_preflight_recheck'} else 'PERSISTENCE_OR_READBACK', False


class PilotStore:
    """Narrow PostgREST boundary; never uses overwrite/estimated-value helpers."""
    def __init__(self, db):
        self.db = db

    def execute(self, make_query):
        # One attempt: a failed/ambiguous write is reported and recovered by a
        # subsequent explicit rerun. No concealed retry can inflate insert counts.
        response = make_query().execute()
        if getattr(response, 'error', None):
            raise PilotBlocked('Database returned an error')
        return response

    def eligibility(self, symbol):
        rows = self.execute(lambda: self.db.get().table('symbols').select('symbol,status,intraday_status')
                            .eq('symbol', symbol)).data
        if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('symbol') != symbol:
            raise PilotBlocked('Requested symbol is missing or ambiguous in symbols master')
        for field in ('status', 'intraday_status'):
            if rows[0].get(field) != 'active':
                raise PilotBlocked(f'Symbol eligibility blocked: {field} must be active')

    def read(self, table, symbol, start, end):
        rows = []
        # Explicit bounded pagination avoids the server's default response cap.
        for offset in range(0, 10000, 100):
            def query():
                q = (self.db.get().table(table).select('*', count='exact').eq('symbol', symbol)
                     .gte('time', start).lt('time', end).order('time'))
                q = q.eq('timeframe', '1m') if table == 'stock_intraday' else q.order('id')
                return q.range(offset, offset + 99)
            response = self.execute(query)
            page = response.data
            if not isinstance(page, list):
                raise PilotBlocked('Database read returned no row representation')
            rows.extend(page)
            if len(page) < 100:
                if not isinstance(response.count, int) or response.count != len(rows):
                    raise PilotBlocked('Incomplete or changing scoped DB count; preflight/readback cannot be trusted')
                return rows
        raise PilotBlocked('Scoped database read exceeded safety bound; no truncated preflight allowed')

    def insert(self, table, records, conflict, acknowledge):
        count = 0
        for offset in range(0, len(records), 100):
            response = self.execute(lambda: self.db.get().table(table).upsert(
                records[offset:offset + 100], on_conflict=conflict, ignore_duplicates=True,
                returning='representation'))
            if not isinstance(response.data, list):
                raise PilotBlocked('Insert outcome unknown; read-only inspection and safe rerun required')
            count += len(response.data)
            acknowledge(len(response.data))
        return count

    def partitions(self, records):
        for month in sorted({instant(row['time'])[:7] for row in records}):
            self.execute(lambda: self.db.get().rpc('create_partition_if_not_exists',
                         {'p_table': 'stock_intraday', 'p_time': f'{month}-01T00:00:00Z'}))


def key(row, raw=False):
    return (row['symbol'], instant(row['time']), row['data_hash'] if raw else row['timeframe'])


def difference(existing, candidate, fields):
    return [field for field in fields if
            (instant(existing.get(field)) if field == 'time' else existing.get(field)) !=
            (instant(candidate.get(field)) if field == 'time' else candidate.get(field))]


def reconcile(existing, candidates, raw=False):
    """No relabeling of identical historical clean rows; source is unknowable."""
    indexed = {}
    for row in existing:
        identity = key(row, raw)
        if identity in indexed:
            raise PilotBlocked('Duplicate existing database identity')
        indexed[identity] = row
    planned, skipped, conflicts = [], 0, []
    for row in candidates:
        old = indexed.get(key(row, raw))
        if old is None:
            planned.append(row)
        else:
            fields = difference(old, row, RAW_FIELDS if raw else CANONICAL)
            if fields:
                conflicts.append({'table': 'stock_raw_intraday' if raw else 'stock_intraday',
                                  'time': row['time'], 'fields': fields})
            else:
                skipped += 1
    if not raw:
        expected = {key(row) for row in candidates}
        conflicts.extend({'table': 'stock_intraday', 'time': row['time'], 'fields': ['unexpected_timestamp']}
                         for row in existing if key(row) not in expected)
    return planned, skipped, conflicts


def candidates(result, symbol, start, end):
    r = result.mapping_report
    if (result.source != 'ssi_v3' or result.dataset != 'stock_intraday' or
        not r.get('pagination_complete') or r.get('pagination_scope') != 'whole_range_from_page_1'):
        raise PilotBlocked('SSI fetch/pagination did not complete the whole date from page 1')
    if (not result.raw or len(result.raw) != len(result.clean) or
        any(row is None for row in result.clean) or result.validation_errors or
        r.get('validation_status') != 'PASS' or r.get('validation_errors')):
        raise PilotBlocked('Every source candle must map and validate; empty/partial batches are blocked')
    if r.get('duplicate_timestamp_count') or r.get('received_order') == 'mixed':
        raise PilotBlocked('Duplicate or mixed timestamp ordering blocks this pilot')
    if r.get('source_value_numeric_valid_count') != len(result.raw):
        raise PilotBlocked('Every source candle requires a valid nonmissing SSI value')
    raw, clean = [], []
    now = datetime.now(timezone.utc).isoformat()
    for payload, mapped in zip(result.raw, result.clean):
        source_symbol = next((v for k, v in payload.items() if k.casefold() == 'symbol'), None)
        if not isinstance(source_symbol, str) or source_symbol.strip().upper() != symbol:
            raise PilotBlocked('Missing or mismatched source symbol identity')
        row = {field: mapped[field] for field in CANONICAL}
        row['time'] = instant(row['time'])
        if (row['symbol'] != symbol or row['timeframe'] != '1m' or
            not start <= datetime.fromisoformat(row['time'].replace('Z', '+00:00')) < end):
            raise PilotBlocked('Mapped candle is outside the exact symbol/Vietnam date/1m scope')
        if type(row['value']) is not int or not 0 <= row['value'] <= 2**63 - 1:
            raise PilotBlocked('Missing/invalid exact source value; estimation is prohibited')
        clean.append({**row, 'created_at': now})
        raw.append({**{f: row[f] for f in ('symbol', 'time', 'open', 'high', 'low', 'close', 'volume')},
                    'data_hash': semantic_hash(payload), 'payload': deepcopy(payload),
                    'source': 'ssi_v3', 'fetched_at': now})
    return raw, clean


def run_manual_intraday(date=None, *, symbols=None, data_source=None, write=False,
                        adapter=None, db=None):
    day, symbol, start, end = scope(date, symbols, data_source)
    if type(write) is not bool:
        raise ValueError('write must be an explicit boolean')
    summary = dict(flow='stock-intraday', mode='WRITE' if write else 'DRY_RUN', date=day,
                   requested_symbols=list(symbols), symbol=symbol, data_source='ssi_v3', status='FAILED',
                   raw_received=0, mapped_valid=0, rejected=0, duplicate_count=0,
                   pagination_complete=False, pagination_termination=None, source_value_valid_count=0,
                   source_value_missing_count=0, source_value_invalid_count=0,
                   raw_inserted=0, raw_skipped_existing=0, clean_inserted=0, clean_skipped_existing=0,
                   planned_raw_insert=None, planned_clean_insert=None, conflict_count=0,
                   readback_raw_count=None, readback_clean_count=None, validation_warnings=[],
                   completeness_status='UNVERIFIED', failures=[], errors=[], conflicts=[],
                   validation_status='NOT_RUN', source_status=None, error_category=None, systemic_failure=False,
                   db_preflight='NOT_RUN', write_ready=False, write_attempted=False,
                   insert_counts_confirmed=True, clean_provenance='Not stored; identical historical rows are not relabeled',
                   utc_scope=[instant(start), instant(end)])
    stage = 'configuration'
    try:
        if db is None and config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
            db = SupabaseClient()
        store = PilotStore(db) if db is not None else None
        if store is None:
            summary['db_preflight'] = 'NOT_RUN_NO_CREDENTIALS'
        if write and store is None:
            raise PilotBlocked('WRITE requires configured Supabase service credentials; no writes attempted')
        if store:
            stage = 'eligibility'
            store.eligibility(symbol)
        stage = 'source_fetch_validation'
        result = (adapter or SSIV3Adapter()).preview_intraday(symbol, day, page_index=1)
        r = result.mapping_report
        summary.update(raw_received=len(result.raw), mapped_valid=r.get('records_valid', 0),
                       validation_status=r.get('validation_status', 'NOT_RUN'), source_status=r.get('status'),
                       rejected=r.get('records_rejected', 0), duplicate_count=r.get('duplicate_timestamp_count', 0),
                       pagination_complete=r.get('pagination_complete', False),
                       pagination_termination=r.get('pagination_termination'),
                       source_value_valid_count=r.get('source_value_numeric_valid_count', 0),
                       source_value_missing_count=r.get('source_value_missing_count', 0),
                       source_value_invalid_count=r.get('source_value_invalid_count', 0),
                       received_order=r.get('received_order'), validation_warnings=r.get('structural_warnings', []),
                       source_diagnostics=r.get('errors', []) + r.get('pagination_diagnostics', []))
        raw, clean = candidates(result, symbol, start, end)
        if store is None:
            summary.update(status='OK', db_preflight='NOT_RUN_NO_CREDENTIALS',
                           source_validated_count=len(clean))
            summary['validation_warnings'].append({'code': 'DB_PREFLIGHT_NOT_RUN',
                'message': 'Eligibility, conflicts and planned insert counts unknown; this is not write approval'})
            return summary
        stage = 'conflict_preflight'
        bounds = (symbol, instant(start), instant(end))
        old_raw = store.read('stock_raw_intraday', *bounds)
        old_clean = store.read('stock_intraday', *bounds)
        raw_plan, raw_skip, raw_conflicts = reconcile(old_raw, raw, raw=True)
        clean_plan, clean_skip, clean_conflicts = reconcile(old_clean, clean)
        conflicts = raw_conflicts + clean_conflicts
        summary.update(conflicts=conflicts, conflict_count=len(conflicts), db_preflight='PASS' if not conflicts else 'BLOCKED',
                       planned_raw_insert=len(raw_plan), planned_clean_insert=len(clean_plan),
                       raw_skipped_existing=raw_skip, clean_skipped_existing=clean_skip)
        if conflicts:
            raise PilotBlocked('Historical raw/clean conflict; no overwrite or force mode is permitted')
        summary['write_ready'] = True
        if not write:
            summary['status'] = 'OK'
            return summary
        # Both payload layers and both conflict checks are complete before this point.
        stage = 'raw_insert'
        def acknowledge_raw(count):
            summary['raw_inserted'] += count
        def acknowledge_clean(count):
            summary['clean_inserted'] += count
        if raw_plan:
            summary['write_attempted'] = True
            store.insert('stock_raw_intraday', raw_plan, 'symbol,time,data_hash', acknowledge_raw)
        stage = 'raw_readback'
        after_raw = store.read('stock_raw_intraday', *bounds)
        missing, _, conflicts = reconcile(after_raw, raw, raw=True)
        summary['readback_raw_count'] = len(after_raw)
        summary['readback_raw_matching_count'] = len(raw) - len(missing) - len(conflicts)
        if missing or conflicts:
            summary.update(conflicts=conflicts, conflict_count=len(conflicts))
            raise PilotBlocked('Raw readback mismatch; clean write was not started')
        summary['raw_skipped_existing'] = len(raw) - summary['raw_inserted']
        # Recheck eligibility and clean conflicts immediately before the clean phase.
        stage = 'clean_preflight_recheck'
        store.eligibility(symbol)
        clean_plan, _, conflicts = reconcile(store.read('stock_intraday', *bounds), clean)
        if conflicts:
            summary.update(conflicts=conflicts, conflict_count=len(conflicts))
            raise PilotBlocked('Concurrent clean conflict after raw; rerun only after owner investigation')
        stage = 'partition'
        if clean_plan:
            summary['write_attempted'] = True
            store.partitions(clean_plan)
        stage = 'clean_insert'
        if clean_plan:
            store.insert('stock_intraday', clean_plan, 'symbol,timeframe,time', acknowledge_clean)
        stage = 'final_readback'
        after_clean = store.read('stock_intraday', *bounds)
        after_raw = store.read('stock_raw_intraday', *bounds)
        missing_clean, _, clean_conflicts = reconcile(after_clean, clean)
        missing_raw, _, raw_conflicts = reconcile(after_raw, raw, raw=True)
        summary.update(readback_raw_count=len(after_raw), readback_clean_count=len(after_clean),
                       conflicts=raw_conflicts + clean_conflicts, conflict_count=len(raw_conflicts + clean_conflicts))
        if missing_raw or missing_clean or raw_conflicts or clean_conflicts or len(after_clean) != len(clean):
            raise PilotBlocked('Final scoped raw/clean count, timestamp or canonical-value readback mismatch')
        summary.update(status='OK', clean_skipped_existing=len(clean) - summary['clean_inserted'],
                       consistency_status='PASS', recovery=None)
    except Exception as exc:
        # Do not expose provider/DB exception bodies (which may contain credentials).
        message = str(exc) if isinstance(exc, PilotBlocked) else f'{type(exc).__name__} during {stage}; inspect sanitized operator logs'
        category, systemic = _failure_category(stage, exc, summary.get('source_diagnostics', []))
        summary.update(status='PARTIAL' if summary['write_attempted'] else 'BLOCKED',
                       error_category=category, systemic_failure=systemic,
                       write_ready=False, failed_stage=stage,
                       errors=[{'stage': stage, 'message': message}], failures=[message],
                       recovery='Inspect this symbol/day read-only, resolve conflicts, then rerun the same command. No cleanup/overwrite is performed.')
        if summary['write_attempted'] and stage in ('raw_insert', 'clean_insert'):
            summary['insert_counts_confirmed'] = False
            summary['insert_count_note'] = 'Counts include acknowledged batches only; failed request may have committed. Readback/rerun required.'
    return summary
