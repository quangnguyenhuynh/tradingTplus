"""Trading-session calendar adapters. Weekdays are deliberately not inferred."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TradingCalendar:
    sessions: tuple[str, ...]
    source: str
    market: str
    identity: str

    def through(self, end: str, count: int) -> list[str]:
        eligible = [day for day in self.sessions if day <= end]
        return eligible[-count:]


def build_calendar(sessions: list[str] | tuple[str, ...], source: str, market: str) -> TradingCalendar:
    if not sessions or not source or not market:
        raise ValueError("calendar requires non-empty sessions, source, and market")
    normalized = tuple(sorted(set(str(value) for value in sessions)))
    if len(normalized) != len(sessions):
        raise ValueError("calendar sessions must be unique")
    identity = hashlib.sha256(
        json.dumps(
            {"sessions": normalized, "source": source, "market": market},
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return TradingCalendar(normalized, str(source), str(market), identity)


def load_calendar(path: str | None) -> TradingCalendar | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sessions = payload.get("sessions")
    source, market = payload.get("source"), payload.get("market")
    if not isinstance(sessions, list):
        raise ValueError("calendar file requires non-empty sessions, source, and market")
    return build_calendar(sessions, str(source or ""), str(market or ""))
