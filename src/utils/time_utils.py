"""Timezone-safe application clock helpers."""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current timezone-aware UTC time in ISO 8601 form."""
    return utc_now().isoformat()
