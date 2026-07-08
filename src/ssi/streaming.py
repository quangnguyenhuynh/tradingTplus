from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlparse

import requests
from src.config import config
from src.ssi.api import SSIApi


class SSIStreamingClient:
    """SSI FCData ASP.NET SignalR (classic) streaming client.

    SSI returns classic SignalR negotiate payloads with ProtocolVersion (for
    example 1.2/2.0) and ConnectionToken, not ASP.NET Core SignalR
    negotiateVersion. Therefore this client intentionally uses requests +
    websocket-client instead of signalrcore.
    """

    def __init__(self, api: SSIApi | None = None) -> None:
        self.api = api or SSIApi()
        self.ws: Any | None = None
        self._websocket_module: Any | None = None
        self.connection_token: str | None = None
        self.connection_id: str | None = None
        self.client_protocol: str | None = None
        self.connection_data: str | None = None
        self.hub_name: str = config.SSI_SIGNALR_HUB
        self._invoke_id = 0
        self.subscribed_channels: list[str] = []

    @property
    def signalr_url(self) -> str:
        return urljoin(config.SSI_STREAMING_BASE_URL.rstrip('/') + '/', config.SSI_SIGNALR_PATH.lstrip('/')).rstrip('/')

    def _headers(self) -> dict[str, str]:
        if not self.api.token:
            raise RuntimeError("SSI token is not initialized")
        return {
            "Authorization": f"Bearer {self.api.token}",
            "Accept": "application/json",
            "User-Agent": "tradingTplus/1.0",
        }

    def _mask_token(self, token: str | None) -> str:
        if not token:
            return "<none>"
        if len(token) <= 12:
            return token[:3] + "***"
        return token[:6] + "***" + token[-6:]

    def _connection_data_json(self, hub_name: str) -> str:
        return json.dumps([{"name": hub_name}], separators=(",", ":"))

    def _negotiate_once(self, protocol: str | None) -> tuple[dict[str, Any], str]:
        base = self.signalr_url + "/negotiate"
        url = base if protocol is None else base + "?" + urlencode({"clientProtocol": protocol})
        print(f"SignalR negotiate url: {url}")
        resp = requests.post(url, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            print(f"❌ negotiate failed status={resp.status_code}")
            print(resp.text[:2000])
            resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            print("❌ negotiate response is not JSON")
            print(resp.text[:2000])
            raise RuntimeError("SignalR negotiate returned non-JSON response") from exc
        return data, url

    def negotiate(self) -> dict[str, Any]:
        attempts: list[str | None] = ["2.1", None, "1.5"]
        last_error: Exception | None = None
        for requested_protocol in attempts:
            try:
                data, _ = self._negotiate_once(requested_protocol)
            except Exception as exc:
                last_error = exc
                continue
            protocol_version = str(data.get("ProtocolVersion") or "")
            if protocol_version == "2.0":
                self.client_protocol = "2.1"
            elif protocol_version == "1.2":
                self.client_protocol = "1.5"
            else:
                self.client_protocol = requested_protocol or "1.5"
            self.connection_id = data.get("ConnectionId")
            self.connection_token = data.get("ConnectionToken")
            print(f"SignalR protocol selected: {self.client_protocol} (server ProtocolVersion={protocol_version or 'unknown'})")
            print(f"ConnectionId: {self.connection_id}")
            print(f"ConnectionToken: {self._mask_token(self.connection_token)}")
            if not self.connection_token:
                raise RuntimeError("SignalR negotiate response missing ConnectionToken")
            return data
        raise RuntimeError(f"SignalR negotiate failed for all protocols: {last_error}")

    def _websocket_base_url(self) -> str:
        parsed = urlparse(self.signalr_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return parsed._replace(scheme=scheme).geturl()

    def _query_params(self) -> dict[str, str]:
        if not self.connection_token or not self.client_protocol or not self.connection_data:
            raise RuntimeError("SignalR connection parameters are not initialized")
        return {
            "transport": "webSockets",
            "clientProtocol": self.client_protocol,
            "connectionToken": self.connection_token,
            "connectionData": self.connection_data,
        }

    def _build_url(self, endpoint: str) -> str:
        params = self._query_params()
        safe = {key: quote(value, safe="") for key, value in params.items()}
        query = "&".join(f"{key}={value}" for key, value in safe.items())
        return f"{self._websocket_base_url()}/{endpoint}?{query}"

    def _build_http_url(self, endpoint: str) -> str:
        params = self._query_params()
        return f"{self.signalr_url}/{endpoint}?" + urlencode(params)

    def _connect_with_hub(self, hub_name: str) -> None:
        self.connection_data = self._connection_data_json(hub_name)
        url = self._build_url("connect")
        safe_url = url.replace(quote(self.connection_token or "", safe=""), "***TOKEN***")
        print(f"SignalR websocket connect URL: {safe_url}")
        try:
            import websocket as websocket_module
        except ImportError as exc:
            raise RuntimeError("Missing dependency websocket-client. Run: pip install websocket-client") from exc
        self._websocket_module = websocket_module
        header = [f"{key}: {value}" for key, value in self._headers().items()]
        self.ws = websocket_module.create_connection(url, header=header, timeout=30)
        self.hub_name = hub_name

    def _start(self) -> None:
        url = self._build_http_url("start")
        safe_url = url.replace(self.connection_token or "", "***TOKEN***")
        print(f"SignalR start url: {safe_url}")
        resp = requests.get(url, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            print(f"❌ SignalR start failed status={resp.status_code}")
            print(resp.text[:2000])
            resp.raise_for_status()
        print(f"SignalR start status: {resp.status_code}; body: {resp.text[:500]}")

    def connect(self) -> None:
        if not config.SSI_STREAMING_ENABLED:
            raise RuntimeError("SSI streaming is disabled by SSI_STREAMING_ENABLED=false")
        self.negotiate()
        errors: list[str] = []
        for hub_name in (config.SSI_SIGNALR_HUB, config.SSI_SIGNALR_HUB.lower()):
            try:
                self._connect_with_hub(hub_name)
                self._start()
                print(f"✅ SignalR classic websocket connected; hub={hub_name}")
                return
            except Exception as exc:
                errors.append(f"{hub_name}: {exc}")
                if self.ws is not None:
                    try:
                        self.ws.close()
                    except Exception:
                        pass
                    self.ws = None
        print("❌ SignalR connect failed")
        print(f"   URL: {self.signalr_url}")
        print(f"   Hub tried: {config.SSI_SIGNALR_HUB}, {config.SSI_SIGNALR_HUB.lower()}")
        print("   Hint: kiểm tra token/quyền streaming/tài khoản FastConnect và clientProtocol.")
        raise RuntimeError("; ".join(errors))

    def close(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            finally:
                self.ws = None

    def subscribe(self, channel: str) -> None:
        if self.ws is None:
            raise RuntimeError("SignalR websocket is not connected")
        self._invoke_id += 1
        payload = {
            "H": self.hub_name,
            "M": config.SSI_SIGNALR_SWITCH_METHOD,
            "A": [channel],
            "I": self._invoke_id,
        }
        self.ws.send(json.dumps(payload, separators=(",", ":")))
        self.subscribed_channels.append(channel)
        print(f"✅ Subscribed channel: {channel}")

    def subscribe_many(self, channels: list[str]) -> None:
        for channel in channels:
            self.subscribe(channel)

    def _extract_broadcast_args(self, raw_text: str) -> list[Any]:
        if raw_text in ("{}", "", None):
            return []
        try:
            message = json.loads(raw_text)
        except (TypeError, json.JSONDecodeError):
            return [raw_text]
        messages = message.get("M") if isinstance(message, dict) else None
        if not messages:
            return []
        output: list[Any] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            if str(item.get("M") or "").lower() != config.SSI_SIGNALR_RECEIVE_METHOD.lower():
                continue
            output.extend(item.get("A") or [])
        return output

    def listen(self, timeout_sec: int, max_messages: int | None = None) -> list[Any]:
        if self.ws is None:
            raise RuntimeError("SignalR websocket is not connected")
        deadline = time.monotonic() + timeout_sec
        collected: list[Any] = []
        self.ws.settimeout(1)
        while time.monotonic() < deadline:
            if max_messages is not None and len(collected) >= max_messages:
                break
            try:
                raw_text = self.ws.recv()
            except Exception as exc:
                timeout_exc = getattr(self._websocket_module, "WebSocketTimeoutException", None)
                if timeout_exc is not None and isinstance(exc, timeout_exc):
                    continue
                print(f"⚠️ websocket receive failed: {exc}")
                break
            args = self._extract_broadcast_args(raw_text)
            if args:
                collected.extend(args)
            elif raw_text not in ("{}", ""):
                # Keep non-heartbeat non-broadcast messages for debug visibility.
                collected.append(raw_text)
        return collected[:max_messages] if max_messages is not None else collected

    def parse_message(self, raw: Any) -> dict[str, Any]:
        return parse_message(raw)

    def collect_latest_by_channels(self, channels: list[str], timeout_sec: int, debug: bool = False) -> dict[str, dict[str, Any]]:
        self.subscribe_many(channels)
        latest: dict[str, dict[str, Any]] = {}
        wanted = {channel.upper(): channel for channel in channels}
        deadline = time.monotonic() + timeout_sec
        first_raw_printed = False
        while time.monotonic() < deadline:
            for raw in self.listen(timeout_sec=1, max_messages=20):
                if debug and not first_raw_printed:
                    print("--- first raw websocket/Broadcast payload ---")
                    print(json.dumps(raw, indent=2, ensure_ascii=False, default=str))
                    first_raw_printed = True
                parsed = self.parse_message(raw)
                normalized = normalize_stream_payload(parsed)
                content = normalized.get("raw") if isinstance(normalized.get("raw"), dict) else parsed
                rtype = str(normalized.get("RType") or normalized.get("DataType") or "").upper()
                symbol = normalized.get("Symbol")
                index_code = normalized.get("IndexId")
                rtype_aliases = {rtype}
                if rtype == "QUOTE":
                    rtype_aliases.add("X-QUOTE")
                elif rtype == "TRADE":
                    rtype_aliases.add("X-TRADE")
                keys = []
                if symbol:
                    keys.extend([f"{alias}:{symbol}".upper() for alias in rtype_aliases])
                    keys.append(str(symbol).upper())
                if index_code:
                    keys.extend([f"{alias}:{index_code}".upper() for alias in rtype_aliases])
                    keys.append(str(index_code).upper())
                matched = None
                for key in keys:
                    if key in wanted:
                        matched = wanted[key]
                        break
                if matched is None and rtype in wanted:
                    matched = wanted[rtype]
                if matched:
                    latest[matched] = content
                    if debug:
                        print("--- normalized stream payload ---")
                        print(json.dumps(normalized, indent=2, ensure_ascii=False, default=str))
                if all(channel in latest for channel in channels):
                    return latest
        return latest

    def collect_latest_quotes(self, symbols: list[str], timeout_sec: int, debug: bool = False) -> dict[str, dict[str, Any]]:
        channels = [f"X-QUOTE:{symbol.upper()}" for symbol in symbols]
        self.subscribe_many(channels)
        latest: dict[str, dict[str, Any]] = {}
        deadline = time.monotonic() + timeout_sec
        first_raw_printed = False
        while time.monotonic() < deadline:
            for raw in self.listen(timeout_sec=1, max_messages=10):
                if debug and not first_raw_printed:
                    print("--- first raw websocket/Broadcast payload ---")
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


def normalize_stream_payload(parsed_message: Any) -> dict[str, Any]:
    """Normalize any SSI market streaming payload without assuming X-QUOTE only."""
    parsed = parsed_message if isinstance(parsed_message, dict) and "content" in parsed_message else parse_message(parsed_message)
    content = parsed.get("content")
    if not isinstance(content, dict):
        return {"RType": parsed.get("data_type"), "DataType": parsed.get("data_type"), "raw": parsed}
    rtype = _get_any(content, "RType", "DataType", "dataType", "type") or parsed.get("data_type")
    symbol = _get_any(content, "Symbol", "symbol")
    index_code = _get_any(content, "IndexId", "IndexID", "indexid", "IndexCode", "indexCode")
    normalized = {
        "RType": rtype,
        "DataType": _get_any(content, "DataType", "dataType") or parsed.get("data_type"),
        "Symbol": str(symbol).upper() if symbol else None,
        "IndexId": str(index_code).upper() if index_code else None,
        "TradingDate": _get_any(content, "TradingDate", "tradingDate"),
        "Time": _get_any(content, "Time", "TradingTime", "time", "tradingTime"),
        "Exchange": _get_any(content, "Exchange", "exchange"),
        "MarketId": _get_any(content, "MarketId", "MarketID", "marketId", "marketid"),
        "raw": content,
    }
    if not normalized["RType"]:
        # Infer from fields as a fallback for SignalR payloads that omit RType.
        if normalized["IndexId"]:
            normalized["RType"] = "MI"
        elif any(_get_any(content, f"BidPrice{i}", f"AskPrice{i}") is not None for i in range(1, 11)):
            normalized["RType"] = "X-QUOTE"
    return normalized
