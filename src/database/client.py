from supabase import create_client
from src.config import config
import pandas as pd
from collections import defaultdict
import time
from datetime import datetime


class SupabaseClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connect()
        return cls._instance
    
    def _connect(self):
        self.client = create_client(
            config.SUPABASE_URL,
            config.SUPABASE_SERVICE_KEY
        )
        print("✅ Kết nối Supabase thành công")
    
    def get(self):
        return self.client

    # =========================================
    # ========== RAW LAYER =====================
    # =========================================
    def insert_raw(self, records):
        if not records:
            return
        
        BATCH_SIZE = 200
        
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i:i+BATCH_SIZE]
            self.client.table('raw_intraday').insert(chunk).execute()
        
        print(f"📦 Đã lưu {len(records)} raw records")

    # =========================================
    # ========== SYMBOLS =======================
    # =========================================
    def upsert_symbols(self, symbols):
        if not symbols:
            return
        
        BATCH_SIZE = 500
        
        for i in range(0, len(symbols), BATCH_SIZE):
            chunk = symbols[i:i+BATCH_SIZE]
            self.client.table('symbols').upsert(chunk).execute()
        
        print(f"📋 Đã lưu {len(symbols)} symbols")

    # =========================================
    # ========== INTRADAY ======================
    # =========================================
    def upsert_intraday(self, records):
        """
        Production version:
        - Normalize UTC
        - Group theo tháng
        - Ensure partition 1 lần / tháng
        - Bulk upsert + retry
        """
        if not records:
            return
        
        print(f"🚀 Start ingest {len(records)} records")

        # -----------------------------
        # 1. Normalize UTC
        # -----------------------------
        for r in records:
            r['time'] = pd.to_datetime(r['time'], utc=True).isoformat()

        # -----------------------------
        # 2. Group theo tháng (cách an toàn hơn)
        # -----------------------------
        buckets = defaultdict(list)
        for r in records:
            # Lấy YYYY-MM từ time đã normalize
            dt = datetime.fromisoformat(r['time'].replace('Z', '+00:00'))
            month = dt.strftime('%Y-%m')
            buckets[month].append(r)

        # -----------------------------
        # 3. Ensure partition (1 lần/tháng)
        # -----------------------------
        for month in buckets.keys():
            try:
                self.client.rpc(
                    'create_partition_if_not_exists',
                    {
                        'p_table': 'stock_intraday',
                        'p_time': f"{month}-01T00:00:00Z"
                    }
                ).execute()
                print(f"📁 Partition OK: {month}")
            except Exception as e:
                print(f"❌ Partition error {month}: {e}")
                raise

        # -----------------------------
        # 4. Bulk upsert
        # -----------------------------
        BATCH_SIZE = 500

        for month, recs in buckets.items():
            print(f"\n📦 Processing {month} ({len(recs)} records)")

            for i in range(0, len(recs), BATCH_SIZE):
                chunk = recs[i:i+BATCH_SIZE]

                retry = 0
                while retry < 3:
                    try:
                        self.client.table('stock_intraday').upsert(
                            chunk,
                            on_conflict='symbol,timeframe,time'
                        ).execute()
                        print(f"✅ Upsert {i} → {i+len(chunk)}")
                        break
                    except Exception as e:
                        retry += 1
                        print(f"⚠️ Retry {retry}: {e}")
                        time.sleep(1)
                        if retry == 3:
                            raise

        print(f"\n🎉 DONE intraday: {len(records)} records")

    # =========================================
    # ========== ORDERBOOK =====================
    # =========================================
    def upsert_orderbook(self, records):
        if not records:
            return
        
        for r in records:
            total_bid = r.get('total_bid_depth_10', 0)
            total_ask = r.get('total_ask_depth_10', 0)
            total = total_bid + total_ask
            
            if total > 0:
                r['orderbook_imbalance'] = total_bid / total
                r['pressure_score'] = (total_bid - total_ask) / total
            else:
                r['orderbook_imbalance'] = 0.5
                r['pressure_score'] = 0

        BATCH_SIZE = 500
        
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i:i+BATCH_SIZE]
            self.client.table('orderbook_snapshot').insert(chunk).execute()
        
        print(f"📖 Đã lưu {len(records)} orderbook snapshots")

    # =========================================
    # ========== FOREIGN =======================
    # =========================================
    def upsert_foreign(self, records):
        if not records:
            return
        
        for r in records:
            r['net_vol'] = r.get('buy_vol', 0) - r.get('sell_vol', 0)

        BATCH_SIZE = 500
        
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i:i+BATCH_SIZE]
            self.client.table('foreign_trading').upsert(
                chunk,
                on_conflict='symbol,time'
            ).execute()
        
        print(f"🌏 Đã lưu {len(records)} foreign trading records")

    # =========================================
    # ========== FEATURES ======================
    # =========================================
    def upsert_features(self, records):
        if not records:
            return
        
        BATCH_SIZE = 500
        
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i:i+BATCH_SIZE]
            self.client.table('features').upsert(
                chunk,
                on_conflict='symbol,timeframe,time'
            ).execute()
        
        print(f"🔧 Đã lưu {len(records)} feature records")

    # =========================================
    # ========== BACKTEST ======================
    # =========================================
    def upsert_backtest(self, records):
        if not records:
            return
        
        BATCH_SIZE = 500
        
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i:i+BATCH_SIZE]
            self.client.table('backtest_data').upsert(
                chunk,
                on_conflict='symbol,timeframe,time'
            ).execute()
        
        print(f"⚡ Đã lưu {len(records)} backtest records")

    # =========================================
    # ========== QUERY =========================
    # =========================================
    def get_symbols(self):
        result = self.client.table('symbols').select('symbol').execute()
        return [row['symbol'] for row in result.data]

    def get_symbol_count(self):
        result = self.client.table('symbols').select('*', count='exact').execute()
        return result.count