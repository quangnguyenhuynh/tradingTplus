from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from src.config import config

SENSITIVE_KEY_PARTS = ("token", "authorization", "consumerid", "consumersecret", "secret")


class InspectorError(RuntimeError):
    pass


@dataclass
class InspectorResponse:
    status_code: int
    elapsed_sec: float
    content_type: str
    body: Any


def is_sensitive_key(key: str) -> bool:
    lowered = key.replace("_", "").replace("-", "").lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, path: str = "") -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if is_sensitive_key(str(key)):
                out[key] = {"redacted": True, "length": len(str(item)) if item is not None else 0, "path": key_path}
            else:
                out[key] = redact(item, key_path)
        return out
    if isinstance(value, list):
        return [redact(item, f"{path}[]") for item in value]
    return value


def find_token_paths(value: Any, path: str = "") -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if is_sensitive_key(str(key)) and item not in (None, ""):
                found.append((key_path, len(str(item))))
            found.extend(find_token_paths(item, key_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(find_token_paths(item, f"{path}[{idx}]"))
    return found


def extract_access_token(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    candidates = [
        value.get("accessToken"), value.get("token"), value.get("Token"),
        (value.get("data") or {}).get("accessToken") if isinstance(value.get("data"), dict) else None,
        (value.get("data") or {}).get("token") if isinstance(value.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


class InspectorClient:
    def __init__(self, timeout: int = 30, session: requests.Session | None = None) -> None:
        self.timeout = max(1, min(int(timeout), 120))
        self.session = session or requests.Session()
        self.token: str | None = None

    def require_credentials(self) -> None:
        if not config.SSI_CONSUMER_ID or not config.SSI_CONSUMER_SECRET:
            raise InspectorError("Missing SSI_CONSUMER_ID/SSI_CONSUMER_SECRET in environment/config")

    def login(self) -> InspectorResponse:
        self.require_credentials()
        payload = {"consumerID": config.SSI_CONSUMER_ID, "consumerSecret": config.SSI_CONSUMER_SECRET}
        response = self._request("POST", config.SSI_AUTH_URL, json=payload, auth=False)
        token = extract_access_token(response.body)
        if not token:
            raise InspectorError("AccessToken response did not contain a recognized token field")
        self.token = token
        return response

    def request_endpoint(self, endpoint: Any, params: dict[str, Any], post_json: dict[str, Any] | None = None) -> InspectorResponse:
        if endpoint.auth_required and not self.token:
            self.login()
        if endpoint.method == "POST":
            return self._request("POST", endpoint.url, json=post_json or {}, auth=endpoint.auth_required)
        response = self._request("GET", endpoint.url, params=params, auth=endpoint.auth_required)
        if response.status_code == 401 and endpoint.auth_required:
            self.login()
            response = self._request("GET", endpoint.url, params=params, auth=True)
        return response

    def _request(self, method: str, url: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None, auth: bool = True) -> InspectorResponse:
        headers = {"Accept": "application/json"}
        if auth:
            if not self.token:
                raise InspectorError("Bearer token is not initialized")
            headers["Authorization"] = f"Bearer {self.token}"
        start = time.perf_counter()
        try:
            resp = self.session.request(method, url, params=params, json=json, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise InspectorError(f"Network error for {method} {url}: {exc}") from exc
        elapsed = time.perf_counter() - start
        try:
            body: Any = resp.json() if resp.text else {}
        except ValueError as exc:
            raise InspectorError(f"Invalid JSON for {method} {url}: {exc}; body={redact(resp.text[:500])}") from exc
        if resp.status_code >= 400 and resp.status_code != 401:
            raise InspectorError(f"HTTP {resp.status_code} for {method} {url}: {redact(body)}")
        return InspectorResponse(resp.status_code, elapsed, resp.headers.get("content-type", ""), body)
