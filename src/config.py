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
    SSI_SECURITIES_DETAILS_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/SecuritiesDetails'
    SSI_INDEX_LIST_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/IndexList'
    SSI_INDEX_COMPONENTS_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/IndexComponents'
    SSI_DAILY_INDEX_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/DailyIndex'
    SSI_DAILY_OHLC_URL = 'https://fc-data.ssi.com.vn/api/v2/Market/DailyOhlc'
    # Official FastConnect Data REST docs do not list a ForeignTrading REST endpoint; foreign fields come from DailyStockPrice.
    # Official docs also do not list a REST orderbook endpoint. Set this only if SSI enables a private/account-specific endpoint.
    SSI_ORDERBOOK_URL = os.getenv('SSI_ORDERBOOK_URL')


config = Config()