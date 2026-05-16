import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Supabase
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    
    # SSI
    SSI_CONSUMER_ID = os.getenv('SSI_CONSUMER_ID')
    SSI_CONSUMER_SECRET = os.getenv('SSI_CONSUMER_SECRET')

     # SSI API URLs
    SSI_API_BASE_URL = 'https://fc-datahub.ssi.com.vn/api/v2/Market'
    SSI_AUTH_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/AccessToken'
    SSI_SECURITIES_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/Securities'
    SSI_DAILY_STOCK_PRICE_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/DailyStockPrice'
    SSI_INTRADAY_OHLC_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/IntradayOhlc'


config = Config()