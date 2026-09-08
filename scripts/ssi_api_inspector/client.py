from __future__ import annotations

import email.utils
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from src.config import config

SENSITIVE_KEY_PARTS = (
    "token", "authorization", "apikey", "apisecret", "consumerid",
    "consumersecret", "privatekey", "password", "secret",
)
RATE_LIMIT_HEADERS = ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset")
SSI_HOSTS = {"api.ssi.com.vn", "fc-data.ssi.com.vn", "fc-datahub.ssi.com.vn"}


class InspectorError(RuntimeError):
    pass


@dataclass
class InspectorResponse:
    status_code: int
    elapsed_sec: float
    content_type: str
    body: Any
    text: str
    json_state: str
    actual_url: str
    rate_limit_headers: dict[str, str]


def is_sensitive_key(key: str) -> bool:
    lowered = key.replace("_", "").replace("-", "").lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, path: str = "") -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            out[key] = ({"redacted": True, "length": len(str(item)) if item is not None else 0, "path": key_path}
                        if is_sensitive_key(str(key)) else redact(item, key_path))
        return out
    if isinstance(value, list):
        return [redact(item, f"{path}[]") for item in value]
    return value


def configured_secrets() -> list[str]:
    return [str(value) for value in (
        config.SSI_API_KEY, config.SSI_API_SECRET,
        config.SSI_CONSUMER_ID, config.SSI_CONSUMER_SECRET,
    ) if value]


def scrub_text(value: str, extra_secrets: list[str] | None = None) -> str:
    result = value
    for secret in sorted({*configured_secrets(), *(extra_secrets or [])}, key=len, reverse=True):
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


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


def _find_named(value: Any, *names: str) -> Any:
    if not isinstance(value, dict):
        return None
    lowered = {str(key).lower(): item for key, item in value.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    for nested in value.values():
        found = _find_named(nested, *names)
        if found not in (None, ""):
            return found
    return None


def extract_access_token(value: Any) -> str | None:
    candidate = _find_named(value, "accessToken", "token")
    return str(candidate) if candidate else None


class InspectorClient:
    def __init__(self, data_source: str = "ssi_v3", timeout: int = 30,
                 session: requests.Session | None = None, max_attempts: int = 3,
                 max_retry_wait: float = 5.0) -> None:
        self.data_source = data_source
        self.timeout = max(1, min(int(timeout), 120))
        self.session = session or requests.Session()
        self.max_attempts = max(1, min(int(max_attempts), 5))
        self.max_retry_wait = max(0.0, min(float(max_retry_wait), 30.0))
        self.token: str | None = None
        self.refresh_token: str | None = None

    def require_credentials(self) -> None:
        if self.data_source == "ssi_v3":
            if not config.SSI_API_KEY or not config.SSI_API_SECRET:
                raise InspectorError("Missing SSI_API_KEY/SSI_API_SECRET for ssi_v3")
        elif not config.SSI_CONSUMER_ID or not config.SSI_CONSUMER_SECRET:
            raise InspectorError("Missing SSI_CONSUMER_ID/SSI_CONSUMER_SECRET for legacy ssi_v2")

    def login(self) -> InspectorResponse:
        self.require_credentials()
        if self.data_source == "ssi_v3":
            url = "https://api.ssi.com.vn/api/v3/auth/token"
            payload = {"apiKey": config.SSI_API_KEY, "apiSecret": config.SSI_API_SECRET}
        else:
            url = config.SSI_AUTH_URL
            payload = {"consumerID": config.SSI_CONSUMER_ID, "consumerSecret": config.SSI_CONSUMER_SECRET}
        response = self._request("POST", url, json=payload, auth=False)
        if response.status_code >= 400:
            raise InspectorError(f"Authentication HTTP {response.status_code}: {self.safe_body(response)}")
        token = extract_access_token(response.body)
        if not token:
            raise InspectorError("Authentication response did not contain accessToken")
        self.token = token
        refresh = _find_named(response.body, "refreshToken")
        self.refresh_token = str(refresh) if refresh else None
        return response

    def request_endpoint(self, endpoint: Any, params: dict[str, Any], post_json: dict[str, Any] | None = None) -> InspectorResponse:
        if endpoint.auth_required and not self.token:
            self.login()
        response = self._request(endpoint.method, endpoint.url, params=params,
                                 json=post_json if endpoint.method == "POST" else None,
                                 auth=endpoint.auth_required)
        if response.status_code == 401 and endpoint.auth_required:
            # Exactly one recovery cycle. Re-login is valid for both sources and
            # avoids persisting either access or refresh tokens.
            self.login()
            response = self._request(endpoint.method, endpoint.url, params=params,
                                     json=post_json if endpoint.method == "POST" else None, auth=True)
        return response

    def _retry_wait(self, response: Any | None, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), self.max_retry_wait)
            except ValueError:
                try:
                    target = email.utils.parsedate_to_datetime(retry_after)
                    return min(max((target - datetime.now(timezone.utc)).total_seconds(), 0.0), self.max_retry_wait)
                except (TypeError, ValueError):
                    pass
        return min(0.25 * (2 ** (attempt - 1)), self.max_retry_wait)

    def _request(self, method: str, url: str, *, params: dict[str, Any] | None = None,
                 json: dict[str, Any] | None = None, auth: bool = True) -> InspectorResponse:
        headers = {"Accept": "application/json"}
        if auth:
            if not self.token:
                raise InspectorError("Bearer token is not initialized")
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(1, self.max_attempts + 1):
            start = time.perf_counter()
            try:
                resp = self.session.request(method, url, params=params, json=json, headers=headers,
                                            timeout=self.timeout, allow_redirects=False)
            except requests.RequestException as exc:
                if attempt < self.max_attempts:
                    time.sleep(self._retry_wait(None, attempt))
                    continue
                raise InspectorError(scrub_text(f"Network error for {method} {url}: {exc}", [self.token or ""])) from exc
            elapsed = time.perf_counter() - start
            if 300 <= resp.status_code < 400:
                raise InspectorError(f"Redirect refused for authenticated SSI request: HTTP {resp.status_code}")
            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                if attempt < self.max_attempts:
                    time.sleep(self._retry_wait(resp, attempt))
                    continue
            raw = resp.text or ""
            if not raw.strip():
                body, json_state = None, "empty"
            else:
                try:
                    body, json_state = resp.json(), "json"
                except ValueError:
                    body, json_state = None, "non-json"
            return InspectorResponse(
                resp.status_code, elapsed, resp.headers.get("content-type", ""), body,
                raw, json_state, getattr(resp, "url", url),
                {key: val for key, val in resp.headers.items() if key.lower() in RATE_LIMIT_HEADERS},
            )
        raise InspectorError("Bounded retry loop ended unexpectedly")

    def safe_body(self, response: InspectorResponse) -> Any:
        secrets = [self.token or "", self.refresh_token or ""]
        if response.json_state == "json":
            return redact(response.body)
        return scrub_text(response.text, secrets)
