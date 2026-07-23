from datetime import timedelta, timezone
from typing import Any

from src.database.client import SupabaseClient
from src.ssi.api import SSIApi
from src.pipeline.daily_service import fetch_daily_for_symbol_with_clients
from src.pipeline.date_utils import latest_previous_weekday, parse_ddmmyyyy, validate_safe_write_date
from src.pipeline.symbol_scope import resolve_symbol_scope, symbol_scope_summary

VN_TZ = timezone(timedelta(hours=7))


def _resolve_daily_date(date: str | None) -> str:
    if date is None:
        resolved = latest_previous_weekday().strftime("%d/%m/%Y")
        print(f"📆 Daily fetch defaulted to latest previous weekday: {resolved}")
        return resolved
    validated = parse_ddmmyyyy(date)
    validate_safe_write_date(validated)
    print(f"📆 Daily fetch: {validated.ddmmyyyy}")
    return validated.ddmmyyyy


def run_daily_ingest(
    date: str | None = None,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Ingest SSI DailyStockPrice for stocks only; never ingest market indexes."""
    date = _resolve_daily_date(date)
    db = SupabaseClient()
    active_symbols, requested_symbols = resolve_symbol_scope(db, symbols)
    scope_summary = symbol_scope_summary(active_symbols, requested_symbols)
    if not active_symbols:
        print("❌ Chưa có dữ liệu symbols. Chạy 'python main.py init' trước!")
        return {
            'date': date,
            **scope_summary,
            'daily_valid_count': 0,
            'total_daily_rows': 0,
            'total_candles': 0,
            'total_foreign': 0,
            'index_daily_count': 0,
            'error_count': 0,
            'error_type_counts': {},
            'errors': [],
            'status': 'FAILED',
        }

    ssi = SSIApi()
    total_daily_rows = 0
    errors: list[dict[str, Any]] = []
    error_type_counts = {key: 0 for key in ("NO_DATA", "API_ERROR", "EMPTY_RESPONSE", "MISMATCH")}
    for symbol in active_symbols:
        try:
            summary = fetch_daily_for_symbol_with_clients(ssi, db, symbol, date)
            total_daily_rows += int(summary.get('daily_rows') or 0)
            if summary.get('status') == 'FAILED':
                error_type = summary.get('error_type') or 'API_ERROR'
                error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
                errors.append({'symbol': symbol, 'error_type': error_type, 'error': '; '.join(summary.get('errors') or ['daily ingest failed'])})
        except Exception as e:
            error_type_counts['API_ERROR'] += 1
            errors.append({'symbol': symbol, 'error_type': 'API_ERROR', 'error': str(e)})
            print(f"    ❌ {symbol}: {e}")

    status = 'OK' if not errors else 'FAILED' if len(errors) >= len(active_symbols) else 'PARTIAL'
    print(f"\n✅ Hoàn thành daily stock ingest! stock_daily rows: {total_daily_rows}; errors: {len(errors)}")
    print("ℹ️ Intraday ingest and feature engine disabled in daily task.")
    return {
        'date': date,
        **scope_summary,
        'daily_valid_count': total_daily_rows,
        'total_daily_rows': total_daily_rows,
        'total_candles': 0,  # deprecated compatibility key; daily no longer writes intraday candles.
        # Normal daily ingest no longer writes foreign_trading. Retained for compatibility;
        # a future breaking cleanup may remove this key.
        'total_foreign': 0,
        # Deprecated compatibility key. Stock-only daily ingest never queries or
        # writes index_daily; remove this key in a future breaking release.
        'index_daily_count': 0,
        'error_count': len(errors),
        'error_type_counts': error_type_counts,
        'errors': errors,
        'status': status,
    }


# Backward-compatible alias for older imports.
daily_run = run_daily_ingest
