from __future__ import annotations

from typing import Any

from src.database.client import SupabaseClient
from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy, validate_safe_write_date
from src.pipeline.fetch_one_day import _parse_trading_date, fetch_intraday_for_symbol_with_clients
from src.ssi.api import SSIApi


def _resolve_intraday_date(date: str | None) -> str:
    if date is None:
        resolved = latest_previous_weekday().strftime("%d/%m/%Y")
        print(f"📆 Intraday ingest defaulted to latest previous weekday: {resolved}")
        return resolved
    validated = parse_ddmmyyyy(date)
    validate_safe_write_date(validated)
    print(f"📆 Intraday ingest: {validated.ddmmyyyy}")
    return validated.ddmmyyyy


def _normalize_symbols(symbols: list[str] | tuple[str, ...] | None) -> list[str] | None:
    if symbols is None:
        return None
    normalized = [str(symbol).upper() for symbol in symbols if str(symbol).strip()]
    return normalized or None


def run_intraday_ingest(date: str | None = None, symbols: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    """Ingest SSI IntradayOhlc 1m only; no daily writes or feature calculation."""
    resolved_date = _resolve_intraday_date(date)
    db = SupabaseClient()
    requested_symbols = _normalize_symbols(symbols)
    active_symbols = requested_symbols or [str(symbol).upper() for symbol in db.get_symbols()]
    if not active_symbols:
        return {
            'date': resolved_date,
            'symbol_count': 0,
            'candles_received': 0,
            'candles_valid': 0,
            'candles_rejected': 0,
            'daily_context_missing_count': 0,
            'errors': [],
            'error_count': 0,
            'status': 'FAILED',
        }

    ssi = SSIApi()
    trading_date = _parse_trading_date(resolved_date)
    totals = {'candles_received': 0, 'candles_valid': 0, 'candles_rejected': 0}
    errors: list[dict[str, str]] = []
    daily_context_missing: list[str] = []
    per_symbol: list[dict[str, Any]] = []
    for symbol in active_symbols:
        try:
            daily_context = db.get_stock_daily(symbol, trading_date)
            if daily_context is None:
                daily_context_missing.append(symbol)
            summary = fetch_intraday_for_symbol_with_clients(ssi, db, symbol, resolved_date, daily_context=daily_context)
            per_symbol.append(summary)
            for key in totals:
                totals[key] += int(summary.get(key) or 0)
            if summary.get('status') == 'FAILED':
                errors.append({'symbol': symbol, 'error': '; '.join(summary.get('errors') or summary.get('warnings') or ['intraday ingest failed'])})
        except Exception as exc:
            errors.append({'symbol': symbol, 'error': str(exc)})
            print(f"    ❌ {symbol}: {exc}")
    status = 'OK' if not errors else 'FAILED' if len(errors) >= len(active_symbols) else 'PARTIAL'
    if status == 'OK' and daily_context_missing:
        status = 'PARTIAL'
    return {
        'date': resolved_date,
        'symbol_count': len(active_symbols),
        **totals,
        'daily_context_missing_count': len(daily_context_missing),
        'daily_context_missing_symbols': daily_context_missing,
        'error_count': len(errors),
        'errors': errors,
        'per_symbol': per_symbol,
        'status': status,
    }
