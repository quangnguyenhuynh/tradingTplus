import logging
import math
import random
import time
import re
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from supabase import create_client

from src.config import config
from src.intraday_value import calculate_trade_value

logger = logging.getLogger(__name__)


_STOCK_INTRADAY_FORBIDDEN_FEATURE_COLUMNS = {
    "value_ma20",
    "value_ratio",
    "cum_value_15m",
    "vwap",
    "vwap_intraday",
    "rsi",
    "rsi14",
    "ema_9",
    "ema_20",
    "ema_50",
    "ema9",
    "ema20",
    "ema50",
}



class SupabaseClient:
    _instance = None
    _CRITICAL_ON_CONFLICT_TABLES = {
        "stock_intraday",
        "features",
        "backtest_data",
        "foreign_trading",
        "orderbook_snapshot",
        "stream_raw_snapshot",
        "stream_quote_snapshot",
        "stream_trade_snapshot",
        "stream_foreign_snapshot",
        "stream_index_snapshot",
        "trading_signals",
        "securities",
        "stock_daily",
        "raw_daily",
        "indexes",
        "index_components",
        "index_daily",
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connect()
        return cls._instance

    def _connect(self):
        self.client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
        logger.info("Supabase connected")

    def reconnect(self):
        logger.warning("Reconnecting Supabase client")
        self._connect()

    def get(self):
        return self.client

    @staticmethod
    def _is_missing_on_conflict_constraint(exc: Exception) -> bool:
        message = str(exc)
        return ("42P10" in message) or bool(re.search(r"no unique|no exclusion|on conflict", message, flags=re.IGNORECASE))

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        error_message = str(exc).lower()
        retry_keys = ["timeout", "connection", "network", "503", "502", "429", "jwt", "auth", "temporarily unavailable"]
        return any(key in error_message for key in retry_keys)

    def _with_retry(self, action, action_name: str, max_retry: int = 3, base_sleep: float = 0.5):
        for attempt in range(1, max_retry + 1):
            try:
                return action()
            except Exception as exc:
                retriable = self._is_retryable_error(exc)
                error_message = str(exc).lower()
                if retriable and ("jwt" in error_message or "auth" in error_message):
                    self.reconnect()

                if attempt >= max_retry or not retriable:
                    logger.exception("%s failed at attempt %s/%s", action_name, attempt, max_retry)
                    raise

                sleep_sec = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.warning("%s retry %s/%s after %.2fs due to: %s", action_name, attempt, max_retry, sleep_sec, exc)
                time.sleep(sleep_sec)

    def health_check(self) -> bool:
        try:
            self._with_retry(
                lambda: self.client.table('symbols').select('symbol').limit(1).execute(),
                action_name="health_check",
                max_retry=2,
                base_sleep=0.2,
            )
            logger.info("Supabase health-check OK")
            return True
        except Exception:
            logger.exception("Supabase health-check failed")
            return False


    @staticmethod
    def _sanitize_for_json(records):
        """Normalize values to JSON-safe Python primitives recursively."""

        def _sanitize_value(value):
            if value is pd.NA or value is pd.NaT:
                return None
            if isinstance(value, dict):
                return {k: _sanitize_value(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_sanitize_value(v) for v in value]
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, pd.Timestamp):
                if pd.isna(value):
                    return None
                return value.isoformat()
            if isinstance(value, np.integer):
                return int(value)
            if isinstance(value, np.floating):
                val = float(value)
                if math.isinf(val) or math.isnan(val):
                    return None
                return val
            if isinstance(value, float):
                if math.isinf(value) or math.isnan(value):
                    return None
                return value
            try:
                if pd.isna(value):
                    return None
            except Exception:
                pass
            return value

        return [_sanitize_value(record) for record in records]

    @staticmethod
    def _extract_missing_column(exc: Exception, table_name: str):
        message = str(exc)
        pattern = rf"Could not find the '([^']+)' column of '{table_name}'"
        match = re.search(pattern, message)
        if match:
            return match.group(1)
        return None

    def _upsert_in_batches(self, table_name: str, records, on_conflict: str | None = None, batch_size: int = 500):
        if not records:
            return

        records = self._sanitize_for_json(records)
        use_on_conflict = bool(on_conflict)

        for i in range(0, len(records), batch_size):
            chunk = records[i:i + batch_size]
            first_symbol = chunk[0].get("symbol") if chunk and isinstance(chunk[0], dict) else None
            times = [
                row.get("time")
                for row in chunk
                if isinstance(row, dict) and row.get("time") is not None
            ]
            min_time = min(times) if times else None
            max_time = max(times) if times else None
            logger.info(
                "Batch upsert table=%s size=%s first_symbol=%s min_time=%s max_time=%s",
                table_name,
                len(chunk),
                first_symbol,
                min_time,
                max_time,
            )

            def _do_upsert():
                query = self.client.table(table_name).upsert(chunk, on_conflict=on_conflict) if use_on_conflict else self.client.table(table_name).upsert(chunk)
                return query.execute()

            try:
                self._with_retry(_do_upsert, action_name=f"upsert {table_name} [{i}:{i + len(chunk)}]")
            except Exception as exc:
                if use_on_conflict and self._is_missing_on_conflict_constraint(exc):
                    if table_name in self._CRITICAL_ON_CONFLICT_TABLES:
                        logger.error(
                            "Missing unique/exclusion constraint for critical table=%s on_conflict=%s. Failing fast.",
                            table_name,
                            on_conflict,
                        )
                        raise

                    logger.warning(
                        "Table %s does not have a unique/exclusion constraint matching on_conflict='%s' (42P10). "
                        "Fallback to upsert without on_conflict for this run.",
                        table_name,
                        on_conflict,
                    )
                    use_on_conflict = False
                    self._with_retry(
                        lambda: self.client.table(table_name).upsert(chunk).execute(),
                        action_name=f"upsert {table_name} [{i}:{i + len(chunk)}] fallback",
                    )
                    continue

                missing_col = self._extract_missing_column(exc, table_name)
                if missing_col:
                    logger.error(
                        "Column '%s' not found in table %s. Schema and code are incompatible; failing fast.",
                        missing_col,
                        table_name,
                    )
                    raise

                raise

        logger.info("Upserted %s records into %s", len(records), table_name)

    def upsert_raw(self, records):
        self._upsert_in_batches('raw_intraday', records, on_conflict='symbol,time,data_hash', batch_size=200)

    def upsert_symbols(self, symbols):
        self._upsert_in_batches('symbols', symbols)

    def upsert_securities(self, records):
        self._upsert_in_batches('securities', records, on_conflict='symbol')

    def upsert_stock_daily(self, records):
        self._upsert_in_batches('stock_daily', records, on_conflict='symbol,trading_date')

    def upsert_raw_daily(self, records):
        self._upsert_in_batches('raw_daily', records, on_conflict='symbol,trading_date,data_hash')

    def upsert_indexes(self, records):
        self._upsert_in_batches('indexes', records, on_conflict='index_code')

    def upsert_index_components(self, records):
        self._upsert_in_batches('index_components', records, on_conflict='index_code,symbol')

    def upsert_index_daily(self, records):
        self._upsert_in_batches('index_daily', records, on_conflict='index_code,trading_date')

    def upsert_intraday(self, records):
        if not records:
            return

        invalid_timeframes = sorted({
            record.get('timeframe')
            for record in records
            if record.get('timeframe') != '1m'
        })
        if invalid_timeframes:
            raise ValueError(
                "stock_intraday is the 1m single source of truth; "
                f"refusing to persist derived timeframes: {invalid_timeframes}"
            )

        forbidden_columns = sorted(
            {column for record in records for column in record}
            & _STOCK_INTRADAY_FORBIDDEN_FEATURE_COLUMNS
        )
        if forbidden_columns:
            raise ValueError(
                "stock_intraday payload contains feature columns that belong in features: "
                f"{forbidden_columns}"
            )

        logger.info("Start ingest %s intraday records", len(records))

        for record in records:
            record['time'] = pd.to_datetime(record['time'], utc=True).isoformat()
            if 'value' not in record or record.get('value') is None:
                record['value'] = calculate_trade_value(record.get('close'), record.get('volume'))

        buckets = defaultdict(list)
        for record in records:
            dt = datetime.fromisoformat(record['time'].replace('Z', '+00:00'))
            buckets[dt.strftime('%Y-%m')].append(record)

        for month in buckets:
            self._with_retry(
                lambda: self.client.rpc(
                    'create_partition_if_not_exists',
                    {'p_table': 'stock_intraday', 'p_time': f"{month}-01T00:00:00Z"},
                ).execute(),
                action_name=f"create partition {month}",
            )

        for month, recs in buckets.items():
            logger.info("Processing month %s with %s records", month, len(recs))
            self._upsert_in_batches('stock_intraday', recs, on_conflict='symbol,timeframe,time')

    def upsert_orderbook(self, records):
        if not records:
            return

        for record in records:
            total_bid = record.get('total_bid_depth_10', 0)
            total_ask = record.get('total_ask_depth_10', 0)
            total = total_bid + total_ask
            if total > 0:
                record['orderbook_imbalance'] = total_bid / total
                record['pressure_score'] = (total_bid - total_ask) / total
            else:
                record['orderbook_imbalance'] = 0.5
                record['pressure_score'] = 0

        allowed = {'symbol', 'time', 'total_bid_depth_10', 'total_ask_depth_10', 'orderbook_imbalance', 'pressure_score', 'raw', 'created_at', 'updated_at'}
        for i in range(1, 11):
            allowed.update({f'bid_price_{i}', f'bid_vol_{i}', f'ask_price_{i}', f'ask_vol_{i}'})
        records = [{key: value for key, value in record.items() if key in allowed} for record in records]
        self._upsert_in_batches('orderbook_snapshot', records, on_conflict='symbol,time')

    def upsert_foreign(self, records):
        if not records:
            return

        for record in records:
            if record.get('foreign_buy_vol') is not None and record.get('buy_vol') is None:
                record['buy_vol'] = record.get('foreign_buy_vol')
            if record.get('foreign_sell_vol') is not None and record.get('sell_vol') is None:
                record['sell_vol'] = record.get('foreign_sell_vol')
            if record.get('net_foreign_vol') is not None and record.get('net_vol') is None:
                record['net_vol'] = record.get('net_foreign_vol')
            if record.get('net_vol') is None and record.get('buy_vol') is not None and record.get('sell_vol') is not None:
                record['net_vol'] = record.get('buy_vol', 0) - record.get('sell_vol', 0)

        on_conflict = 'symbol,trading_date' if any(record.get('trading_date') for record in records) else 'symbol,time'
        self._upsert_in_batches('foreign_trading', records, on_conflict=on_conflict)

    def upsert_stream_raw(self, records):
        self._upsert_in_batches('stream_raw_snapshot', records, on_conflict='channel,time')

    def upsert_stream_quote(self, records):
        self._upsert_in_batches('stream_quote_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_trade(self, records):
        self._upsert_in_batches('stream_trade_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_foreign_snapshot(self, records):
        self._upsert_in_batches('stream_foreign_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_index_snapshot(self, records):
        self._upsert_in_batches('stream_index_snapshot', records, on_conflict='index_code,time')

    def upsert_features(self, records):
        self._upsert_in_batches('features', records, on_conflict='symbol,timeframe,time')

    def upsert_backtest(self, records):
        self._upsert_in_batches('backtest_data', records, on_conflict='symbol,timeframe,time')

    def get_symbols(self):
        result = self._with_retry(lambda: self.client.table('symbols').select('symbol').execute(), action_name="get_symbols")
        return [row['symbol'] for row in result.data]

    def get_symbol_count(self):
        result = self._with_retry(
            lambda: self.client.table('symbols').select('*', count='exact').execute(),
            action_name="get_symbol_count",
        )
        return result.count
