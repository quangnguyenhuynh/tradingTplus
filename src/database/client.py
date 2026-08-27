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
from src.utils.time_utils import app_now_iso

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
        "stock_features",
        "stock_foreign_trading",
        "stock_orderbook_snapshot",
        "stream_raw_snapshot",
        "stream_quote_snapshot",
        "stream_trade_snapshot",
        "stream_foreign_snapshot",
        "stream_index_snapshot",
        "stream_status_snapshot",
        "stream_bar_snapshot",
        "securities",
        "stock_daily",
        "stock_raw_daily",
        "stock_raw_intraday",
        "index_master",
        "index_components",
        "index_raw_daily",
        "index_daily",
        "index_features_daily",
    }
    _CREATED_AT_TABLES = {
        "symbols",
        "stock_raw_daily",
        "index_raw_daily",
        "stock_daily",
        "stock_intraday",
        "stock_orderbook_snapshot",
        "stream_raw_snapshot",
        "stream_quote_snapshot",
        "stream_trade_snapshot",
        "stream_foreign_snapshot",
        "stream_index_snapshot",
        "stream_status_snapshot",
        "stream_bar_snapshot",
        "stock_data_quality_logs",
        "index_features_daily",
    }
    _UPDATED_AT_TABLES = {
        "stock_daily",
        "stock_intraday",
        "securities",
        "index_master",
        "index_components",
        "stock_foreign_trading",
        "stock_orderbook_snapshot",
        "index_features_daily",
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
        # NOT NULL violations are deterministic payload/schema errors. Some
        # PostgREST messages include request/connection wording in their details,
        # so classify the PostgreSQL code before looking for transient keywords.
        if "23502" in error_message:
            return False
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

    @classmethod
    def _stamp_write_timestamps(cls, table_name: str, records, now_iso: str | None = None):
        """Copy records and add application-controlled persistence timestamps."""
        stamp = now_iso or app_now_iso()
        stamped = [dict(record) for record in records]
        for record in stamped:
            if table_name in cls._CREATED_AT_TABLES:
                # Application-controlled creation timestamps are mandatory. Treat an
                # explicit None like an omitted value rather than sending JSON null.
                if record.get("created_at") is None:
                    record["created_at"] = stamp
            if table_name in cls._UPDATED_AT_TABLES:
                record["updated_at"] = stamp
            if table_name == "stock_raw_intraday":
                record["fetched_at"] = stamp
            if table_name == "stream_raw_snapshot":
                record.setdefault("received_at", stamp)
            if table_name == "stock_features":
                record["last_updated_at"] = stamp
        return stamped

    def _upsert_in_batches(self, table_name: str, records, on_conflict: str | None = None, batch_size: int = 500):
        if not records:
            return

        records = self._sanitize_for_json(
            self._stamp_write_timestamps(table_name, records, app_now_iso())
        )
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
                if table_name in self._CREATED_AT_TABLES and use_on_conflict:
                    # First insert new rows with the app timestamp without touching conflicts.
                    self.client.table(table_name).upsert(
                        chunk,
                        on_conflict=on_conflict,
                        ignore_duplicates=True,
                    ).execute()
                    if table_name == "index_raw_daily":
                        # Raw index evidence is immutable and the identity includes its
                        # payload hash. There are no mutable columns to update. A second
                        # bulk upsert that omits created_at is unsafe because PostgREST can
                        # materialize the missing field as NULL (default_to_null behavior).
                        return None
                    # Then update all mutable fields while omitting created_at. Existing rows
                    # retain their original creation time; newly inserted rows keep the stamp.
                    update_chunk = [
                        {key: value for key, value in row.items() if key != "created_at"}
                        for row in chunk
                    ]
                    query = self.client.table(table_name).upsert(
                        update_chunk,
                        on_conflict=on_conflict,
                    )
                else:
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
        self._upsert_in_batches('stock_raw_intraday', records, on_conflict='symbol,time,data_hash', batch_size=200)

    def _load_master_statuses(self, table_name: str, key_column: str, keys) -> dict[str, str]:
        """Load current operator status so master sync never reactivates disabled rows."""
        normalized_keys = [str(key) for key in keys if key not in (None, "")]
        statuses: dict[str, str] = {}
        for offset in range(0, len(normalized_keys), 200):
            chunk = normalized_keys[offset:offset + 200]
            result = self._with_retry(
                lambda chunk=chunk: self.client.table(table_name)
                .select(f'{key_column},status')
                .in_(key_column, chunk)
                .execute(),
                action_name=f"load {table_name} statuses [{offset}:{offset + len(chunk)}]",
            )
            statuses.update({
                str(row[key_column]): str(row['status'])
                for row in (result.data or [])
                if row.get(key_column) not in (None, "") and row.get('status') in {'active', 'inactive'}
            })
        return statuses

    def _preserve_master_status(self, table_name: str, key_column: str, records):
        existing = self._load_master_statuses(
            table_name,
            key_column,
            [record.get(key_column) for record in records],
        )
        prepared = []
        for record in records:
            row = dict(record)
            key = str(row[key_column])
            row['status'] = row.get('status') or existing.get(key, 'active')
            prepared.append(row)
        return prepared

    def upsert_symbols(self, symbols):
        records = self._preserve_master_status('symbols', 'symbol', symbols)
        self._upsert_in_batches('symbols', records, on_conflict='symbol')

    def upsert_securities(self, records):
        self._upsert_in_batches('securities', records, on_conflict='symbol')

    def upsert_stock_daily(self, records):
        self._upsert_in_batches('stock_daily', records, on_conflict='symbol,trading_date')

    def upsert_raw_daily(self, records):
        self._upsert_in_batches('stock_raw_daily', records, on_conflict='symbol,trading_date,data_hash')

    def upsert_index_master(self, records):
        prepared = self._preserve_master_status('index_master', 'index_code', records)
        self._upsert_in_batches('index_master', prepared, on_conflict='index_code')

    def upsert_indexes(self, records):
        """Deprecated compatibility alias for pre-migration callers."""
        return self.upsert_index_master(records)

    def upsert_index_components(self, records):
        self._upsert_in_batches('index_components', records, on_conflict='index_code,symbol')

    def upsert_index_daily(self, records):
        self._upsert_in_batches('index_daily', records, on_conflict='index_code,trading_date')

    def upsert_index_raw_daily(self, records):
        self._upsert_in_batches('index_raw_daily', records, on_conflict='index_code,trading_date,data_hash')

    def upsert_index_features_daily(self, records):
        """Persist only the dedicated index feature identity."""
        self._upsert_in_batches(
            'index_features_daily', records, on_conflict='index_code,trading_date'
        )

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

        normalized_records = []
        for source_record in records:
            record = dict(source_record)
            record['time'] = pd.to_datetime(record['time'], utc=True).isoformat()
            if 'value' not in record or record.get('value') is None:
                record['value'] = calculate_trade_value(record.get('close'), record.get('volume'))
            normalized_records.append(record)

        buckets = defaultdict(list)
        for record in normalized_records:
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
        self._upsert_in_batches('stock_orderbook_snapshot', records, on_conflict='symbol,time')

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
        self._upsert_in_batches('stock_foreign_trading', records, on_conflict=on_conflict)

    def upsert_stream_raw(self, records):
        self._upsert_in_batches('stream_raw_snapshot', records, on_conflict='payload_hash')

    def upsert_stream_quote(self, records):
        self._upsert_in_batches('stream_quote_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_trade(self, records):
        self._upsert_in_batches('stream_trade_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_foreign_snapshot(self, records):
        self._upsert_in_batches('stream_foreign_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_index_snapshot(self, records):
        self._upsert_in_batches('stream_index_snapshot', records, on_conflict='index_code,time')

    def upsert_stream_status_snapshot(self, records):
        self._upsert_in_batches('stream_status_snapshot', records, on_conflict='symbol,time')

    def upsert_stream_bar_snapshot(self, records):
        self._upsert_in_batches('stream_bar_snapshot', records, on_conflict='symbol,time')

    def upsert_features(self, records):
        self._upsert_in_batches('stock_features', records, on_conflict='symbol,timeframe,time')

    def atomic_replace_features(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_utc: str,
        end_exclusive_utc: str,
        replacement_rows: list[dict],
    ) -> dict:
        """Invoke the single-transaction scoped feature replacement RPC."""
        rows = self._sanitize_for_json(replacement_rows)
        response = self._with_retry(
            lambda: self.client.rpc(
                "replace_features_atomic",
                {
                    "p_symbol": symbol,
                    "p_timeframe": timeframe,
                    "p_start_utc": start_utc,
                    "p_end_exclusive_utc": end_exclusive_utc,
                    "p_replacement_rows": rows,
                },
            ).execute(),
            action_name=(
                "replace_features_atomic "
                f"symbol={symbol} timeframe={timeframe} start={start_utc} "
                f"end_exclusive={end_exclusive_utc} rows={len(rows)}"
            ),
        )
        data = response.data or []
        summary = data[0] if isinstance(data, list) and data else data
        if not isinstance(summary, dict):
            raise RuntimeError("replace_features_atomic returned an invalid summary")
        return {
            "deleted_rows": int(summary.get("deleted_count", 0)),
            "replaced_rows": int(summary.get("replaced_count", 0)),
        }

    def get_symbols(self):
        result = self._with_retry(
            lambda: self.client.table('symbols')
            .select('symbol')
            .eq('status', 'active')
            .order('symbol')
            .execute(),
            action_name="get active symbols",
        )
        return [row['symbol'] for row in result.data]

    def get_stock_daily(self, symbol: str, trading_date: str | None):
        if not trading_date:
            return None
        result = self._with_retry(
            lambda: self.client.table('stock_daily').select('*').eq('symbol', symbol.upper()).eq('trading_date', trading_date).limit(1).execute(),
            action_name=f"get_stock_daily {symbol.upper()} {trading_date}",
        )
        rows = result.data or []
        return rows[0] if rows else None

    def get_symbol_count(self):
        result = self._with_retry(
            lambda: self.client.table('symbols').select('*', count='exact').execute(),
            action_name="get_symbol_count",
        )
        return result.count
