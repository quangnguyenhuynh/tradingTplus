"""Timezone-safe application clock helpers for persistence audit fields."""
from datetime import datetime
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def app_now() -> datetime:
    """Return the current application time as an aware Vietnam datetime."""
    return datetime.now(APP_TZ)


def app_now_iso() -> str:
    """Return application time as ISO 8601 with the explicit ``+07:00`` offset."""
    return app_now().isoformat()
