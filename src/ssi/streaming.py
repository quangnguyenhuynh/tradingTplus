from __future__ import annotations

import json
import time
from typing import Any, Iterable


from src.config import config
from src.ssi.api import SSIApi


_DATA_TYPE_MAP = {
    "X": "Quote",
    "X-QUOTE": "Quote",
    "QUOTE": "Quote",
    "T": "Trade",
    "X-TRADE": "Trade",
    "TRADE": "Trade",
    "B": "B",
    "R": "R",
    "MI": "MI",
}


def _get_any(data: dict, *keys: str) -> Any:
    lowered = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _loads_maybe_json(value: Any) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_data_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return _DATA_TYPE_MAP.get(text.upper(), text)


class SSIStreamingClient:
    def __init__(self, url: str | None = None, ssi_api: SSIApi | None = None, reconnect: bool = True) -> None:
        if not config.SSI_STREAMING_ENABLED:
            raise RuntimeError("SSI streaming is disabled by SSI_STREAMING_ENABLED")
        self.url = url or config.SSI_STREAMING_URL
        if not self.url:
            raise RuntimeError("SSI_STREAMING_URL is not configured")
        self.ssi_api = ssi_api or SSIApi()
        self.reconnect = reconnect
        self.ws = None
        self._channels: list[str] = []

    def connect(self) -> None:
        token = self.ssi_api.token
        if not token:
            raise RuntimeError("SSI token is not available for streaming connection")
        headers = [f"Authorization: Bearer {token}"]
        print(f"🔌 Connecting SSI streaming: {self.url}")
        import websocket
        self.ws = websocket.create_connection(self.url, header=headers, timeout=config.ORDERBOOK_SNAPSHOT_TIMEOUT_SEC)
        print("✅ SSI streaming connected")

    def close(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            finally:
                self.ws = None
                print("🔌 SSI streaming closed")

    def _ensure_connected(self) -> None:
        if self.ws is None:
            self.connect()

    def _reconnect_and_resubscribe(self) -> None:
        if not self.reconnect:
            raise RuntimeError("SSI streaming connection lost and reconnect is disabled")
        print("🔄 Reconnecting SSI streaming...")
        self.close()
        time.sleep(1)
        self.connect()
        for channel in self._channels:
            self._send_subscribe(channel)

    def _send_subscribe(self, channel: str) -> None:
        self._ensure_connected()
        print(f"📡 Subscribe SSI streaming channel: {channel}")
        self.ws.send(channel)

    def subscribe(self, channel: str) -> None:
        if channel not in self._channels:
            self._channels.append(channel)
        self._send_subscribe(channel)

    def subscribe_many(self, channels: Iterable[str]) -> None:
        for channel in channels:
            self.subscribe(channel)

    def recv_raw(self, timeout: float | None = None) -> Any:
        self._ensure_connected()
        if timeout is not None:
            self.ws.settimeout(timeout)
        try:
            return self.ws.recv()
        except Exception:
            if self.reconnect:
                self._reconnect_and_resubscribe()
                if timeout is not None:
                    self.ws.settimeout(timeout)
                return self.ws.recv()
            raise

    def listen(self, timeout_sec: float, max_messages: int | None = None):
        deadline = time.monotonic() + timeout_sec
        count = 0
        while time.monotonic() < deadline:
            if max_messages is not None and count >= max_messages:
                break
            remaining = max(0.1, deadline - time.monotonic())
            raw = self.recv_raw(timeout=remaining)
            count += 1
            yield self.parse_message(raw)

    @staticmethod
    def parse_message(raw_message: Any) -> dict:
        original_raw = raw_message
        outer = _loads_maybe_json(raw_message)
        if not isinstance(outer, dict):
            return {"data_type": None, "content": {"value": outer}, "raw": original_raw}

        content = _get_any(outer, "Content", "content", "data", "payload")
        content = _loads_maybe_json(content)
        if content is None:
            content = outer
        if not isinstance(content, dict):
            content = {"value": content}

        data_type = _normalize_data_type(
            _get_any(outer, "DataType", "datatype", "type", "RType", "rtype")
            or _get_any(content, "DataType", "datatype", "type", "RType", "rtype")
        )
        return {"data_type": data_type, "content": content, "raw": original_raw}


def normalize_quote(parsed_message: dict) -> dict | None:
    content = parsed_message.get("content") if isinstance(parsed_message, dict) else None
    if not isinstance(content, dict):
        return None
    data_type = _normalize_data_type(parsed_message.get("data_type") or _get_any(content, "RType", "type"))
    if data_type not in (None, "Quote", "X", "B", "R") and str(data_type).upper() not in ("QUOTE", "X-QUOTE"):
        return None
    symbol = _get_any(content, "Symbol", "symbol")
    if not symbol:
        return None
    normalized = {
        "Symbol": str(symbol).upper(),
        "TradingDate": _get_any(content, "TradingDate", "tradingDate"),
        "Time": _get_any(content, "Time", "TradingTime", "time"),
        "Exchange": _get_any(content, "Exchange", "exchange"),
        "TradingSession": _get_any(content, "TradingSession", "tradingSession"),
        "TradingStatus": _get_any(content, "TradingStatus", "tradingStatus"),
        "LastPrice": _get_any(content, "LastPrice", "Last", "Close", "lastPrice"),
        "TotalVol": _get_any(content, "TotalVol", "totalVol"),
        "TotalVal": _get_any(content, "TotalVal", "totalVal"),
    }
    for i in range(1, 11):
        normalized[f"BidPrice{i}"] = _get_any(content, f"BidPrice{i}", f"Bid{i}", f"bidPrice{i}")
        normalized[f"BidVol{i}"] = _get_any(content, f"BidVol{i}", f"BidVolume{i}", f"bidVol{i}", f"bidVolume{i}")
        normalized[f"AskPrice{i}"] = _get_any(content, f"AskPrice{i}", f"Ask{i}", f"askPrice{i}")
        normalized[f"AskVol{i}"] = _get_any(content, f"AskVol{i}", f"AskVolume{i}", f"askVol{i}", f"askVolume{i}")
    normalized["raw"] = content
    return normalized
