"""Runtime configuration for SSI v3 and existing Supabase persistence."""
import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    SSI_API_KEY = os.getenv("SSI_API_KEY")
    SSI_API_SECRET = os.getenv("SSI_API_SECRET")

config = Config()
