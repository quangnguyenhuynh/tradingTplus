import logging
import random
import time
from collections import defaultdict
from datetime import datetime

import pandas as pd
from supabase import create_client

from src.config import config

logger = logging.getLogger(__name__)


class SupabaseClient:
    _instance = None

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

    def _with_retry(self, action, action_name: str, max_retry: int = 3, base_sleep: float = 0.5):
        for attempt in range(1, max_retry + 1):
            try:
                return action()
            except Exception as exc:
                error_message = str(exc).lower()
                retriable = any(k in error_message for k in ["timeout", "connection", "network", "503", "502", "429", "jwt", "auth"])
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

    def _upsert_in_batches(self, table_name: str, records, on_conflict: str | None = None, batch_size: int = 500):
        if not records:
            return

        for i in range(0, len(records), batch_size):
            chunk = records[i:i + batch_size]

            def _do_upsert():
                query = self.client.table(table_name).upsert(chunk, on_conflict=on_conflict) if on_conflict else self.client.table(table_name).upsert(chunk)
                return query.execute()

            self._with_retry(_do_upsert, action_name=f"upsert {table_name} [{i}:{i + len(chunk)}]")

        logger.info("Upserted %s records into %s", len(records), table_name)

    def upsert_raw(self, records):
        self._upsert_in_batches('raw_intraday', records, on_conflict='symbol,time,data_hash', batch_size=200)

    def upsert_symbols(self, symbols):
        self._upsert_in_batches('symbols', symbols)

    def upsert_intraday(self, records):
        if not records:
            return

        logger.info("Start ingest %s intraday records", len(records))

        for record in records:
            record['time'] = pd.to_datetime(record['time'], utc=True).isoformat()

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

        self._upsert_in_batches('orderbook_snapshot', records, on_conflict='symbol,time')

    def upsert_foreign(self, records):
        if not records:
            return

        for record in records:
            record['net_vol'] = record.get('buy_vol', 0) - record.get('sell_vol', 0)

        self._upsert_in_batches('foreign_trading', records, on_conflict='symbol,time')

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
