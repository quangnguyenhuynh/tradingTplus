"""Read-only Phase 0 schema, payload-lineage, and sample reconciliation checks."""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from src.ingest.stock_daily.daily_mapper import build_stock_daily_record
from src.contracts.intraday_preview import map_intraday_preview

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UTC = ZoneInfo("UTC")
STATUS_ORDER = {"PASS": 0, "WARNING": 1, "UNKNOWN": 2, "FAIL": 3}
OHLCV = ("open", "high", "low", "close", "volume")


def _result(status: str, check: str, **details: Any) -> dict[str, Any]:
    return {"status": status, "check": check, **details}


def overall_status(results: Iterable[dict[str, Any]]) -> str:
    statuses = [row["status"] for row in results]
    return max(statuses, key=STATUS_ORDER.get) if statuses else "UNKNOWN"


def verify_schema(connection: Any) -> dict[str, Any]:
    """Inspect PostgreSQL catalogs only; this function never invokes the RPC."""
    checks: list[dict[str, Any]] = []
    with connection.cursor() as cursor:
        cursor.execute("""
          select data_type, is_nullable, column_default
          from information_schema.columns
          where table_schema='public' and table_name='stock_raw_intraday'
            and column_name='payload'
        """)
        row = cursor.fetchone()
        checks.append(_result(
            "PASS" if row == ("jsonb", "YES", None) else "FAIL",
            "stock_raw_intraday.payload",
            observed=row,
            expected=["jsonb", "YES", None],
            reason="Nullable JSONB without default matches the historical-payload contract" if row == ("jsonb", "YES", None) else "Missing column or incompatible payload type/nullability/default",
        ))
        cursor.execute("""
          select p.prosecdef, p.proconfig,
            has_function_privilege('service_role', p.oid, 'execute'),
            has_function_privilege('anon', p.oid, 'execute'),
            has_function_privilege('authenticated', p.oid, 'execute'),
            exists(select 1 from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                   where a.grantee=0 and a.privilege_type='EXECUTE')
          from pg_proc p join pg_namespace n on n.oid=p.pronamespace
          where n.nspname='public' and p.proname='replace_features_atomic'
            and pg_get_function_identity_arguments(p.oid) =
              'p_symbol text, p_timeframe text, p_start_utc timestamp with time zone, p_end_exclusive_utc timestamp with time zone, p_replacement_rows jsonb'
        """)
        function_row = cursor.fetchone()
        safe_search_path = bool(
            function_row and function_row[1]
            and any(value in {'search_path=""', 'search_path='} for value in function_row[1])
        )
        function_ok = bool(function_row and function_row[0] and safe_search_path
                           and function_row[2] and not any(function_row[3:]))
        checks.append(_result(
            "PASS" if function_ok else "FAIL",
            "replace_features_atomic security",
            expected={"signature": "(text,text,timestamptz,timestamptz,jsonb)", "security_definer": True,
                      "search_path": "empty", "execute": "service_role only; not PUBLIC/anon/authenticated"},
            observed=function_row,
            reason="Expected signature and restricted security contract verified" if function_ok else "Missing expected signature or unsafe execution/search_path properties",
            exists=function_row is not None,
            security_definer=bool(function_row and function_row[0]),
            search_path=(function_row[1] if function_row else None),
            service_role_execute=bool(function_row and function_row[2]),
            anon_execute=bool(function_row and function_row[3]),
            authenticated_execute=bool(function_row and function_row[4]),
            public_execute=bool(function_row and function_row[5]),
        ))
        cursor.execute("""
          select idx.relname, i.indisunique, i.indisvalid, i.indisready,
                 i.indpred is null, i.indexprs is null,
                 array(select a.attname::text
                       from unnest(i.indkey) with ordinality k(attnum, position)
                       join pg_attribute a on a.attrelid=i.indrelid and a.attnum=k.attnum
                       where k.position <= i.indnkeyatts order by k.position)
          from pg_index i join pg_class t on t.oid=i.indrelid
          join pg_namespace n on n.oid=t.relnamespace
          join pg_class idx on idx.oid=i.indexrelid
          where n.nspname='public' and t.relname='stock_features'
        """)
        indexes = cursor.fetchall()
        matching = [row[0] for row in indexes
                    if all(row[1:6]) and len(row[6]) == 3
                    and set(row[6]) == {'symbol', 'timeframe', 'time'}]
        checks.append(_result(
            "PASS" if matching else "FAIL", "stock_features unique index",
            matching_indexes=matching, expected_columns=["symbol", "timeframe", "time"],
            expected="Valid, ready, nonpartial, nonexpression UNIQUE key on exactly symbol/timeframe/time; PK/constraint-backed indexes accepted",
            observed=indexes,
            reason="Canonical unique identity verified" if matching else "No valid full unique canonical identity found",
        ))
    return {"status": overall_status(checks), "checks": checks, "read_only": True}


def _vn_bounds(trading_date: date) -> tuple[str, str]:
    start = datetime.combine(trading_date, time.min, tzinfo=VN_TZ).astimezone(UTC)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def check_intraday_payload(client: Any, *, symbol: str | None = None,
                            trading_date: date | None = None) -> dict[str, Any]:
    """Find a bounded non-null payload sample; historical NULLs are informational."""
    query = client.table("stock_raw_intraday").select("symbol,time,payload,fetched_at")
    if symbol:
        query = query.eq("symbol", symbol.upper())
    if trading_date:
        start, end = _vn_bounds(trading_date)
        query = query.gte("time", start).lt("time", end)
    rows = (query.order("fetched_at", desc=True).limit(100).execute().data or [])
    non_null = next((row for row in rows if row.get("payload") is not None), None)
    null_count = sum(row.get("payload") is None for row in rows)
    if non_null:
        return _result("PASS", "intraday payload sample", sample={
            "symbol": non_null.get("symbol"), "time": non_null.get("time"),
            "fetched_at": non_null.get("fetched_at"),
        }, inspected_rows=len(rows), historical_null_rows=null_count,
                       historical_null_policy="EXPECTED_NO_BACKFILL", read_only=True)
    return _result("UNKNOWN", "intraday payload sample", inspected_rows=len(rows),
                   historical_null_rows=null_count,
                   reason="No non-null payload exists in the bounded selected sample",
                   historical_null_policy="EXPECTED_NO_BACKFILL", read_only=True)


def numeric_equal(left: Any, right: Any, tolerance: float) -> bool:
    if left is None or right is None:
        return left is right
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, abs_tol=tolerance, rel_tol=tolerance)


def _instant(value: Any) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must be a valid timezone-aware ISO instant") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return stamp.astimezone(UTC)


def _integer(value: Any) -> int:
    # Never round a float or allow tolerance to hide a BIGINT discrepancy.
    if isinstance(value, (bool, float)):
        raise ValueError("exact integer representation required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("exact integer required") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("finite integer required")
    return int(number)


def compare_fields(expected: dict[str, Any], actual: dict[str, Any], fields: Iterable[str],
                   tolerance: float, *, exact_intraday: bool = False) -> list[dict[str, Any]]:
    comparisons = []
    for field in fields:
        left, right = expected.get(field), actual.get(field)
        if field in {'symbol', 'timeframe', 'trading_date'}:
            equal = left == right
        elif field == 'time':
            try:
                equal = _instant(left) == _instant(right)
            except ValueError:
                equal = False
        elif exact_intraday and field in {'volume', 'value'}:
            try:
                equal = (left is right) if left is None or right is None else _integer(left) == _integer(right)
            except ValueError:
                equal = False
        else:
            equal = numeric_equal(left, right, tolerance)
        comparisons.append(dict(field=field, expected=left, actual=right, match=equal))
    return comparisons


class _EvidenceUnavailable(ValueError):
    pass


def validate_reconciliation_scope(symbol: str, trading_date: date, timeframe: str,
                                  timestamp: str | None, tolerance: float) -> str:
    """Pure validation shared by the CLI before client construction."""
    symbol = symbol.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,19}', symbol) or symbol == 'ALL':
        raise ValueError('one concrete stock symbol is required')
    if timeframe not in {'1m', '1d', '15m', '60m'}:
        raise ValueError('timeframe must be one of: 1m, 1d, 15m, 60m')
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('tolerance must be finite and nonnegative')
    if timestamp and _instant(timestamp).astimezone(VN_TZ).date() != trading_date:
        raise ValueError('timestamp must belong to the requested Vietnam trading date')
    return symbol


def _rows(client: Any, table: str, filters: list[tuple[str, str, Any]], *, bound: int) -> list[dict]:
    """Read one explicit symbol/day, paginated and bounded, never silently capped."""
    rows = []
    for offset in range(0, bound, 100):
        query = client.table(table).select('*', count='exact')
        for operation, field, value in filters:
            query = getattr(query, operation)(field, value)
        if table in {'stock_raw_daily', 'stock_daily'}:
            query = query.order('trading_date')
            if table == 'stock_raw_daily':
                query = query.order('data_hash')
        else:
            query = query.order('time')
            if table == 'stock_raw_intraday':
                query = query.order('id')
        response = query.range(offset, offset + 99).execute()
        page = response.data
        total = response.count
        if not isinstance(page, list) or not isinstance(total, int) or len(rows) + len(page) > bound:
            raise _EvidenceUnavailable(f'{table}: missing exact count or bounded response')
        rows.extend(page)
        if total > bound:
            raise _EvidenceUnavailable(f'{table}: selected day exceeds diagnostic bound {bound}')
        if len(rows) == total:
            return rows
        if len(page) != 100 or len(rows) > total:
            raise _EvidenceUnavailable(f'{table}: truncated/changing read; evidence is incomplete')
    raise _EvidenceUnavailable(f'{table}: diagnostic bound reached')


def _issue(code: str, reason: str, status: str = 'UNKNOWN', **details) -> dict:
    return dict(status=status, code=code, reason=reason, **details)


def _layer(comparisons: list[dict], issues: list[dict]) -> dict:
    status = overall_status([*issues, *([{'status': 'FAIL'}] if any(not r['match'] for r in comparisons) else [])])
    if not issues and comparisons:
        status = 'FAIL' if any(not r['match'] for r in comparisons) else 'PASS'
    return dict(status=status, comparisons=comparisons, diagnostics=issues)


def _raw_intraday(raw_rows: list[dict], clean_rows: list[dict], symbol: str,
                  day: date, tolerance: float) -> dict:
    comparisons, issues = [], []
    raw_by_time, clean_by_time = {}, {}
    for rows, target in ((raw_rows, raw_by_time), (clean_rows, clean_by_time)):
        for row in rows:
            target.setdefault(_instant(row['time']), []).append(row)
    if not raw_rows:
        issues.append(_issue('RAW_MISSING', 'stock_raw_intraday has no exact matching source evidence'))
    if not clean_rows:
        issues.append(_issue('CLEAN_MISSING', 'stock_intraday has no exact matching 1m row'))
    for stamp in sorted(set(raw_by_time) | set(clean_by_time)):
        sources, cleans = raw_by_time.get(stamp, []), clean_by_time.get(stamp, [])
        if len(cleans) > 1:
            issues.append(_issue('DUPLICATE_CLEAN_IDENTITY', 'Multiple canonical 1m rows at the same instant', 'FAIL', time=stamp.isoformat()))
        if len(sources) > 1:
            issues.append(_issue('RAW_AMBIGUOUS', 'Multiple raw versions/sources at the exact instant; no arbitrary selection', time=stamp.isoformat(), sources=[r.get('source') for r in sources]))
            continue
        if not sources:
            issues.append(_issue('RAW_MISSING', 'No raw evidence for clean instant', time=stamp.isoformat()))
            continue
        raw = sources[0]
        if raw.get('source') != 'ssi_v3':
            issues.append(_issue('SOURCE_UNSUPPORTED', 'Retired/unknown raw source is not remapped as SSI v3', source=raw.get('source'), time=stamp.isoformat()))
            continue
        if raw.get('payload') is None:
            issues.append(_issue('RAW_PAYLOAD_MISSING', 'Historical NULL payload is permitted, but cannot be reconciled', time=stamp.isoformat()))
            continue
        mapped, reports = map_intraday_preview([raw['payload']], symbol, day.isoformat(), day.isoformat(), source='ssi_v3')
        candidate = mapped[0]
        if candidate is None:
            issues.append(_issue('SOURCE_PAYLOAD_INCOMPATIBLE', 'Persisted payload cannot be verified with the SSI v3 contract', time=stamp.isoformat(), mapping_errors=reports[0]['errors']))
            continue
        # Verify the stored raw identity against the payload even if clean is absent.
        comparisons.extend({**r, 'sample_time': stamp.isoformat(), 'target': 'raw_identity'}
                           for r in compare_fields(candidate, raw, ('symbol', 'time'), tolerance, exact_intraday=True))
        if len(cleans) == 1:
            comparisons.extend({**r, 'sample_time': stamp.isoformat(), 'target': 'clean'} for r in
                               compare_fields(candidate, cleans[0], ('symbol', 'timeframe', 'time', *OHLCV, 'value'), tolerance, exact_intraday=True))
        elif not cleans:
            issues.append(_issue('CLEAN_MISSING', 'No exact canonical clean row; no nearby timestamp substitution', time=stamp.isoformat()))
    return _layer(comparisons, issues)


def _sample_raw(rows: list[dict], timestamp: str | None) -> list[dict]:
    if timestamp:
        stamp = _instant(timestamp)
    elif rows:
        preferred = [row for row in rows if row.get('source') == 'ssi_v3'] or rows
        stamp = min(_instant(row['time']) for row in preferred)
    else:
        return []
    return [row for row in rows if _instant(row['time']) == stamp]


def _feature_layer(clean_rows: list[dict], feature: dict | None, timeframe: str,
                   tolerance: float) -> dict:
    if feature is None:
        return _layer([], [_issue('FEATURE_MISSING', 'features: no exact selected feature bucket')])
    if not clean_rows:
        return _layer([], [_issue('CLEAN_MISSING', 'stock_intraday: no observed clean rows for feature bucket')])
    stamps = [_instant(row['time']) for row in clean_rows]
    if len(stamps) != len(set(stamps)):
        return _layer([], [_issue('DUPLICATE_CLEAN_IDENTITY', 'Duplicate 1m timestamps cannot be deduplicated for diagnostics', 'FAIL')])
    unknown_fields = sorted({field for row in clean_rows for field in (*OHLCV, 'value') if row.get(field) is None})
    if unknown_fields:
        # aggregate_timeframe uses a legacy missing-value estimate internally;
        # do not invoke it at all on incomplete values or pretend NULL is zero.
        return _layer([], [_issue('AGGREGATION_EVIDENCE_MISSING', 'NULL source fields prevent independent aggregation; no estimate/zero fill', fields=unknown_fields)])
    from src.features.stock.intraday import aggregate_timeframe, filter_closed_buckets
    import pandas as pd

    for row in clean_rows:
        for field in ('open', 'high', 'low', 'close'):
            if isinstance(row[field], bool) or not numeric_equal(row[field], row[field], 0):
                return _layer([], [_issue('INVALID_CLEAN_PRICE', 'Cannot aggregate nonfinite/invalid clean price', 'FAIL', field=field)])
        for field in ('volume', 'value'):
            try:
                if _integer(row[field]) < 0:
                    raise ValueError('negative canonical total')
            except ValueError:
                return _layer([], [_issue('INVALID_CLEAN_INTEGER', 'Cannot verify exact integer aggregate', 'FAIL', field=field)])
    aggregate = aggregate_timeframe(pd.DataFrame(clean_rows), timeframe)
    stamp = _instant(feature['time'])
    selected = aggregate.loc[aggregate['time'] == pd.Timestamp(stamp)]
    if len(selected) != 1:
        return _layer([], [_issue('BUCKET_IDENTITY_MISMATCH', 'Feature timestamp does not match an observed bucket under the existing VN session convention', 'FAIL')])
    if filter_closed_buckets(selected, timeframe, pd.Timestamp.now(tz=VN_TZ)).empty:
        return _layer([], [_issue('BUCKET_NOT_CLOSED', 'Partially formed/open feature bucket is not independently reconciled')])
    expected = selected.iloc[0].to_dict()
    # Preserve exact Python integer sums even near BIGINT bounds, avoiding numpy overflow.
    expected.update(volume=sum(_integer(r['volume']) for r in clean_rows),
                    value=sum(_integer(r['value']) for r in clean_rows), symbol=feature['symbol'], timeframe=timeframe)
    return _layer(compare_fields(expected, feature, ('symbol', 'timeframe', 'time', *OHLCV, 'value'), tolerance, exact_intraday=True), [])


def reconcile_sample(client: Any, *, symbol: str, trading_date: date, timeframe: str,
                     timestamp: str | None = None, tolerance: float = 1e-6) -> dict[str, Any]:
    """Read-only bounded lineage checks; never call SSI, ingest or feature computation."""
    symbol = validate_reconciliation_scope(symbol, trading_date, timeframe, timestamp, tolerance)
    start, end = _vn_bounds(trading_date)
    layers, missing, feature, selected_time = {}, [], None, None
    try:
        scope = [('eq', 'symbol', symbol)]
        day_scope = [*scope, ('gte', 'time', start), ('lt', 'time', end)]
        feature_scope = [*day_scope, ('eq', 'timeframe', timeframe)]
        if timestamp:
            feature_scope.append(('eq', 'time', _instant(timestamp).isoformat()))
        if timeframe == '1d':
            daily_scope = [*scope, ('eq', 'trading_date', trading_date.isoformat())]
            raws = _rows(client, 'stock_raw_daily', daily_scope, bound=1000)
            cleans = _rows(client, 'stock_daily', daily_scope, bound=100)
            features = _rows(client, 'stock_features', feature_scope, bound=100)
            raw_issues, raw_comparisons = [], []
            preferred = [r for r in raws if r.get('source') == 'ssi_v3'] or raws
            raw = preferred[0] if len(preferred) == 1 and len(raws) == 1 else None
            clean = cleans[0] if len(cleans) == 1 else None
            feature = features[0] if len(features) == 1 else None
            if not raws: missing.append('stock_raw_daily.payload')
            if not cleans: missing.append('stock_daily')
            if not features: missing.append('features')
            if len(raws) > 1: raw_issues.append(_issue('RAW_AMBIGUOUS', 'Multiple daily raw versions/sources'))
            if raw is None and not raws: raw_issues.append(_issue('RAW_MISSING', 'stock_raw_daily.payload missing'))
            if len(cleans) > 1: raw_issues.append(_issue('DUPLICATE_CLEAN_IDENTITY', 'Multiple daily clean rows', 'FAIL'))
            if raw:
                if raw.get('source') != 'ssi_v3':
                    raw_issues.append(_issue('SOURCE_UNSUPPORTED', 'Daily raw source is retired or unknown'))
                elif not isinstance(raw.get('payload'), dict):
                    raw_issues.append(_issue('RAW_PAYLOAD_MISSING', 'stock_raw_daily.payload missing'))
                else:
                    mapped = build_stock_daily_record(symbol, trading_date.strftime('%d/%m/%Y'), raw['payload'])
                    if mapped is None:
                        raw_issues.append(_issue('SOURCE_PAYLOAD_INCOMPATIBLE', 'Daily payload cannot be mapped with the actual v3 contract'))
                    elif clean:
                        raw_comparisons = compare_fields(mapped, clean, ('symbol', 'trading_date', 'open_price', 'highest_price', 'lowest_price', 'close_price', 'total_traded_vol', 'total_traded_value'), tolerance)
            if clean is None: raw_issues.append(_issue('CLEAN_MISSING', 'stock_daily unavailable or ambiguous'))
            layers['raw_to_clean'] = _layer(raw_comparisons, raw_issues)
            if clean and feature:
                expected = dict(open=clean.get('open_price'), high=clean.get('highest_price'), low=clean.get('lowest_price'), close=clean.get('close_price'), volume=clean.get('total_traded_vol'), value=clean.get('total_traded_value'))
                layers['clean_to_feature'] = _layer(compare_fields(expected, feature, (*OHLCV, 'value'), tolerance), [])
            else:
                layers['clean_to_feature'] = _layer([], [_issue('FEATURE_AMBIGUOUS' if len(features) > 1 else 'FEATURE_OR_CLEAN_MISSING', 'Daily feature/clean evidence missing or ambiguous')])
        else:
            exact_scope = [*day_scope, *([('eq', 'time', _instant(timestamp).isoformat())] if timestamp and timeframe == '1m' else [])]
            raws = _rows(client, 'stock_raw_intraday', exact_scope, bound=3000)
            cleans = _rows(client, 'stock_intraday', [*exact_scope, ('eq', 'timeframe', '1m')], bound=2000)
            if timeframe == '1m':
                selected = _sample_raw(raws, timestamp)
                stamp = (_instant(timestamp) if timestamp else _instant(selected[0]['time']) if selected else
                         min((_instant(r['time']) for r in cleans), default=None))
                selected_time = stamp.isoformat() if stamp else None
                selected_clean = [r for r in cleans if _instant(r['time']) == stamp]
                layers['raw_to_clean'] = _raw_intraday(selected, selected_clean, symbol, trading_date, tolerance)
                layers['clean_to_feature'] = dict(status='NOT_APPLICABLE', comparisons=[], diagnostics=[], reason='Canonical 1m does not require a stock_features row')
            else:
                features = _rows(client, 'stock_features', feature_scope, bound=200)
                if features:
                    latest = max(_instant(r['time']) for r in features)
                    selected = [r for r in features if _instant(r['time']) == latest]
                    if len(selected) > 1:
                        layers['clean_to_feature'] = _layer([], [_issue('FEATURE_AMBIGUOUS', 'Multiple feature rows at selected canonical bucket', 'FAIL')])
                    else:
                        feature = selected[0]
                        bucket_start = _instant(feature['time'])
                        bucket_end = bucket_start + timedelta(minutes=int(timeframe[:-1]))
                        in_bucket = lambda row: (bucket_start <= _instant(row['time']) < bucket_end and
                            (_instant(row['time']).astimezone(VN_TZ).hour >= 12) == (bucket_start.astimezone(VN_TZ).hour >= 12))
                        raw_bucket = [r for r in raws if in_bucket(r)]
                        clean_bucket = [r for r in cleans if in_bucket(r)]
                        selected_time = bucket_start.isoformat()
                        layers['raw_to_clean'] = _raw_intraday(raw_bucket, clean_bucket, symbol, trading_date, tolerance)
                        layers['clean_to_feature'] = _feature_layer(clean_bucket, feature, timeframe, tolerance)
                if not feature:
                    missing.append('features')
                    layers.setdefault('clean_to_feature', _layer([], [_issue('FEATURE_MISSING', 'features missing')]))
                    sample = _sample_raw(raws, None)
                    stamps = {_instant(r['time']) for r in sample}
                    layers['raw_to_clean'] = _raw_intraday(sample, [r for r in cleans if _instant(r['time']) in stamps], symbol, trading_date, tolerance)
    except _EvidenceUnavailable as exc:
        layers['evidence'] = _layer([], [_issue('BOUNDED_READ_INCOMPLETE', str(exc))])
    except Exception as exc:
        # Remote exception bodies can contain URLs/credentials; retain type/stage only.
        layers['evidence'] = _layer([], [_issue('READ_OR_CONTRACT_ERROR', f'{type(exc).__name__}: persisted evidence could not be read/verified; no writes performed')])
    comparisons = [{**row, 'layer': name} for name, layer in layers.items() for row in layer['comparisons']]
    diagnostics = [row for layer in layers.values() for row in layer['diagnostics']]
    missing.extend(row['reason'] for row in diagnostics if row['status'] == 'UNKNOWN' and row['reason'] not in missing)
    # Verified mismatches outrank missing/unsupported evidence, never the reverse.
    status = overall_status([layer for layer in layers.values() if layer['status'] != 'NOT_APPLICABLE'])
    return _result(status, 'sample reconciliation', symbol=symbol, date=trading_date.isoformat(), timeframe=timeframe,
                   feature_time=feature.get('time') if feature else None, selected_time=selected_time,
                   sample_selection='Exact instant when supplied; otherwise earliest ssi_v3 raw instant (1m), latest feature bucket (15m/60m); all collisions reported',
                   tolerance=tolerance, integer_comparison='exact; no float conversion or tolerance',
                   layers=layers, comparisons=comparisons, missing=missing, read_only=True, coverage_status='UNVERIFIED')
