from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any
from urllib.parse import urljoin

from src.config import config
from src.ssi.api import SSIApi


class SSIStreamingClient:
    """SSI FCData SignalR streaming client.

    SSI streaming uses a SignalR hub, not a raw websocket URL. This client follows
    the official shape: base URL + `v2.0/signalr`, hub `FcMarketDataV2Hub`, receive
    method `Broadcast`, and subscribe/switch method `SwitchChannels`.
    """

    def __init__(self, api: SSIApi | None = None) -> None:
        self.api = api or SSIApi()
        self.hub_connection = None
        self.messages: queue.Queue[Any] = queue.Queue()
        self._connected = False
        self._lock = threading.Lock()
        self.subscribed_channels: list[str] = []

    @property
    def signalr_url(self) -> str:
        return urljoin(config.SSI_STREAMING_BASE_URL.rstrip('/') + '/', config.SSI_SIGNALR_PATH.lstrip('/'))

    def _headers(self) -> dict[str, str]:
        if not self.api.token:
            raise RuntimeError("SSI token is not initialized")
        return {
            "Authorization": f"Bearer {self.api.token}",
            "Accept": "application/json",
        }

    def _on_message(self, *args: Any) -> None:
        payload: Any = list(args) if len(args) != 1 else args[0]
        self.messages.put(payload)

    def connect(self) -> None:
        if not config.SSI_STREAMING_ENABLED:
            raise RuntimeError("SSI streaming is disabled by SSI_STREAMING_ENABLED=false")
        try:
            from signalrcore.hub_connection_builder import HubConnectionBuilder
        except ImportError as exc:
            raise RuntimeError("Missing dependency signalrcore. Run: pip install signalrcore") from exc

        try:
            self.hub_connection = (
                HubConnectionBuilder()
                .with_url(self.signalr_url, options={"headers": self._headers()})
                .with_automatic_reconnect({"type": "raw", "keep_alive_interval": 10, "reconnect_interval": 5, "max_attempts": 5})
                .build()
            )
            self.hub_connection.on(config.SSI_SIGNALR_RECEIVE_METHOD, self._on_message)
            self.hub_connection.start()
            with self._lock:
                self._connected = True
        except Exception as exc:
            print("❌ SignalR connect failed")
            print(f"   URL: {self.signalr_url}")
            print(f"   Hub: {config.SSI_SIGNALR_HUB}")
            print("   Hint: kiểm tra token/quyền streaming/tài khoản FastConnect và network/proxy.")
            raise

    def close(self) -> None:
        if self.hub_connection is not None:
            try:
                self.hub_connection.stop()
            finally:
                with self._lock:
                    self._connected = False

    def subscribe(self, channel: str) -> None:
        if not self.hub_connection or not self._connected:
            raise RuntimeError("SignalR client is not connected")
        self.hub_connection.send(config.SSI_SIGNALR_SWITCH_METHOD, [channel])
        self.subscribed_channels.append(channel)
        print(f"✅ Subscribed channel: {channel}")

    def subscribe_many(self, channels: list[str]) -> None:
        for channel in channels:
            self.subscribe(channel)

    def listen(self, timeout_sec: int, max_messages: int | None = None) -> list[Any]:
        deadline = time.monotonic() + timeout_sec
        collected: list[Any] = []
        while time.monotonic() < deadline:
            if max_messages is not None and len(collected) >= max_messages:
                break
            remaining = max(0.1, min(1.0, deadline - time.monotonic()))
            try:
                collected.append(self.messages.get(timeout=remaining))
            except queue.Empty:
                continue
        return collected

    def parse_message(self, raw: Any) -> dict[str, Any]:
        return parse_message(raw)

    def collect_latest_quotes(self, symbols: list[str], timeout_sec: int, debug: bool = False) -> dict[str, dict[str, Any]]:
        channels = [f"X-QUOTE:{symbol.upper()}" for symbol in symbols]
        self.subscribe_many(channels)
        latest: dict[str, dict[str, Any]] = {}
        deadline = time.monotonic() + timeout_sec
        first_raw_printed = False
        while time.monotonic() < deadline:
            for raw in self.listen(timeout_sec=1, max_messages=10):
                if debug and not first_raw_printed:
                    print("--- first raw callback ---")
                    print(json.dumps(raw, indent=2, ensure_ascii=False, default=str))
                    first_raw_printed = True
                parsed = self.parse_message(raw)
                quote = normalize_quote(parsed)
                symbol = quote.get("symbol")
                if symbol:
                    latest[symbol] = quote
                    if debug:
                        print("--- parsed message ---")
                        print(json.dumps(parsed, indent=2, ensure_ascii=False, default=str))
                        print("--- normalized quote ---")
                        print(json.dumps(quote, indent=2, ensure_ascii=False, default=str))
                if all(symbol.upper() in latest for symbol in symbols):
                    return latest
        return latest


def _json_loads_maybe(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def parse_message(raw: Any) -> dict[str, Any]:
    original = raw
    if isinstance(raw, (list, tuple)):
        if len(raw) == 1:
            raw = raw[0]
        elif len(raw) >= 2:
            raw = {"data_type": raw[0], "content": raw[1], "args": list(raw)}
    raw = _json_loads_maybe(raw)
    data_type = None
    content: Any = raw
    if isinstance(raw, dict):
        data_type = raw.get("DataType") or raw.get("datatype") or raw.get("dataType") or raw.get("type") or raw.get("RType")
        for key in ("Content", "content", "Data", "data", "payload", "Payload"):
            if key in raw:
                content = raw[key]
                break
    content = _json_loads_maybe(content)
    if isinstance(content, dict) and data_type is None:
        data_type = content.get("DataType") or content.get("datatype") or content.get("dataType") or content.get("type") or content.get("RType")
    return {"data_type": data_type, "content": content, "raw": original}


def _get_any(data: dict, *keys: str) -> Any:
    lowered = {str(k).lower(): v for k, v in (data or {}).items()}
    for key in keys:
        if key in data:
            return data.get(key)
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def normalize_quote(parsed: dict[str, Any]) -> dict[str, Any]:
    content = parsed.get("content")
    if not isinstance(content, dict):
        return {"raw": parsed}
    quote = {
        "data_type": parsed.get("data_type"),
        "symbol": _get_any(content, "Symbol", "symbol"),
        "trading_date": _get_any(content, "TradingDate", "tradingDate"),
        "time": _get_any(content, "Time", "TradingTime", "time", "tradingTime"),
        "exchange": _get_any(content, "Exchange", "exchange"),
        "trading_session": _get_any(content, "TradingSession", "tradingSession"),
        "trading_status": _get_any(content, "TradingStatus", "tradingStatus"),
        "last_price": _get_any(content, "LastPrice", "Last", "LastMatchedPrice", "lastPrice"),
        "total_vol": _get_any(content, "TotalVol", "totalVol"),
        "total_val": _get_any(content, "TotalVal", "totalVal"),
        "raw": content,
    }
    if quote["symbol"]:
        quote["symbol"] = str(quote["symbol"]).upper()
    for level in range(1, 11):
        quote[f"bid_price_{level}"] = _get_any(content, f"BidPrice{level}", f"bidPrice{level}")
        quote[f"bid_vol_{level}"] = _get_any(content, f"BidVol{level}", f"BidVolume{level}", f"bidVol{level}", f"bidVolume{level}")
        quote[f"ask_price_{level}"] = _get_any(content, f"AskPrice{level}", f"askPrice{level}")
        quote[f"ask_vol_{level}"] = _get_any(content, f"AskVol{level}", f"AskVolume{level}", f"askVol{level}", f"askVolume{level}")
    return quote
