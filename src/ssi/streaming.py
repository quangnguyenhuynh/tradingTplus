from __future__ import annotations

import json
import time
from typing import Any, Iterable

from src.config import config
from src.ssi.api import SSIApi

try:
    import websocket
except ImportError:  # pragma: no cover - exercised only when dependency missing in runtime env
    websocket = None


class SSIStreamingQuoteClient:
    """Minimal SSI FCData quote streaming client.

    The quote stream emits market data messages where the actual quote can be an
    outer JSON object with `Content`/`content` containing an inner JSON string.
    This client subscribes to X-QUOTE and yields normalized quote dictionaries.
    """

    def __init__(self, url: str | None = None, api: SSIApi | None = None, timeout_sec: int | None = None) -> None:
        self.url = url or config.SSI_STREAMING_URL
        self.api = api or SSIApi()
        self.timeout_sec = timeout_sec or config.ORDERBOOK_SNAPSHOT_TIMEOUT_SEC
        self.ws = None

    def connect(self) -> None:
        if not config.SSI_STREAMING_ENABLED:
            raise RuntimeError("SSI_STREAMING_ENABLED=false; streaming quote snapshot is disabled")
        if not self.url:
            raise RuntimeError("SSI_STREAMING_URL chưa cấu hình, không thể lấy orderbook snapshot từ official REST")
        if websocket is None:
            raise RuntimeError("Missing dependency websocket-client. Install requirements.txt before using SSI streaming.")
        headers = [f"Authorization: Bearer {self.api.token}"] if self.api.token else []
        self.ws = websocket.create_connection(self.url, header=headers, timeout=self.timeout_sec)

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
            self.ws = None

    def subscribe_quote(self, symbols: Iterable[str] | str) -> None:
        if self.ws is None:
            raise RuntimeError("Streaming socket is not connected")
        if isinstance(symbols, str):
            symbol_text = symbols.upper()
        else:
            values = [str(symbol).upper() for symbol in symbols]
            symbol_text = "ALL" if values == ["ALL"] else ",".join(values)
        # SSI docs describe X-QUOTE:<symbol|ALL>. JSON envelope keeps it explicit
        # while remaining easy to inspect in websocket logs.
        message = {"type": "X-QUOTE", "symbol": symbol_text, "symbols": symbol_text}
        self.ws.send(json.dumps(message))

    @staticmethod
    def _loads_maybe_json(value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return value
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
        return value

    @classmethod
    def parse_message(cls, message: str | bytes | dict) -> dict | None:
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="replace")
        outer = cls._loads_maybe_json(message)
        if not isinstance(outer, dict):
            return None
        content = None
        lowered = {str(key).lower(): value for key, value in outer.items()}
        for key in ("content", "data", "message", "payload"):
            if key in lowered:
                content = lowered[key]
                break
        inner = cls._loads_maybe_json(content) if content is not None else outer
        if isinstance(inner, dict):
            return inner
        return outer

    @staticmethod
    def quote_symbol(quote: dict) -> str | None:
        lowered = {str(key).lower(): value for key, value in quote.items()}
        value = lowered.get("symbol") or lowered.get("ticker")
        return str(value).upper() if value else None

    @staticmethod
    def is_quote_message(quote: dict) -> bool:
        lowered = {str(key).lower(): value for key, value in quote.items()}
        rtype = str(lowered.get("rtype") or lowered.get("type") or "").upper()
        return rtype in ("X", "X-QUOTE", "QUOTE") or any(key.startswith("bidprice") or key.startswith("askprice") for key in lowered)

    def collect_latest_quotes(self, symbols: list[str], timeout_sec: int | None = None, debug: bool = False) -> dict[str, dict]:
        if self.ws is None:
            self.connect()
        target = {symbol.upper() for symbol in symbols}
        latest: dict[str, dict] = {}
        deadline = time.time() + (timeout_sec or self.timeout_sec)
        while time.time() < deadline and target - set(latest):
            try:
                raw_message = self.ws.recv()
            except Exception as exc:
                print(f"⚠️ Streaming recv warning: {exc}")
                break
            quote = self.parse_message(raw_message)
            if not quote or not self.is_quote_message(quote):
                continue
            symbol = self.quote_symbol(quote)
            if not symbol:
                continue
            if debug:
                print("🔎 Raw quote payload:")
                print(json.dumps(quote, indent=2, ensure_ascii=False, default=str))
            if symbol in target:
                latest[symbol] = quote
        return latest
