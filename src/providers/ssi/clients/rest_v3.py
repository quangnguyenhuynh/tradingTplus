"""Bounded, read-only SSI v3 REST client (no database dependencies)."""
from __future__ import annotations
import time
import json
from decimal import Decimal
from email.utils import parsedate_to_datetime
from datetime import timezone
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import requests
from src.config import config

BASE = "https://api.ssi.com.vn/api/v3"


def reject_json_constant(value):
    raise ValueError('Non-finite JSON constant')


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key')
        result[key] = value
    return result


def master_retry_delay(response, attempt):
    """Respect Retry-After up to 30s; a larger wait fails instead of retrying early."""
    header = response.headers.get('Retry-After')
    if header is None:
        return min(.25 * 2 ** (attempt - 1), 4)
    try:
        delay = float(header)
    except (TypeError, ValueError):
        try:
            moment = parsedate_to_datetime(header)
            if moment.tzinfo is None:
                return None
            delay = (moment - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0, delay) if 0 <= delay <= 30 else None


class SSIReadError(RuntimeError):
    def __init__(self, message: str = "", *, response_body=None, code=None):
        super().__init__(message)
        self.response_body = response_body
        self.code = code


def provider_date(value: str) -> str:
    """Normalize an accepted CLI/internal date to SSI v3's date format."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y/%m/%d")
        except ValueError:
            pass
    raise ValueError(f"Invalid date {value!r}; use DD/MM/YYYY or YYYY-MM-DD")


def securities_summary_params(
    symbol: str,
    from_date: str,
    to_date: str | None = None,
    *,
    page_index: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """Build the single SSI v3 securitiesSummary request contract."""
    return {
        "symbol": symbol,
        "from": provider_date(from_date),
        "to": provider_date(to_date or from_date),
        "pageIndex": page_index,
        "pageSize": page_size,
    }


def _safe_request_params(params: Any) -> Any:
    if not isinstance(params, dict):
        return params
    sensitive = ("authorization", "token", "secret", "apikey", "consumerid")
    return {
        key: "[REDACTED]"
        if any(marker in str(key).replace("_", "").casefold() for marker in sensitive)
        else _safe_request_params(value)
        for key, value in params.items()
    }


def _envelope_error(body: Any) -> tuple[Any, Any]:
    if not isinstance(body, dict):
        return None, None
    lowered = {str(key).casefold(): value for key, value in body.items()}
    code = next((lowered[key] for key in ("code", "statuscode", "errorcode", "responsecode") if key in lowered), None)
    message = next((lowered[key] for key in ("msg", "message", "error") if key in lowered), None)
    return code, message


def _request_error(method: str, path: str, params: Any, status: int, body: Any = None) -> SSIReadError:
    code, message = _envelope_error(body)
    detail = (
        f"endpoint={method} /api/v3{path} params={_safe_request_params(params)!r} "
        f"http_status={status}"
    )
    if code is not None:
        detail += f" api_code={code!r}"
    if message is not None:
        detail += f" api_msg={message!r}"
    return SSIReadError(f"SSI request failed: {detail}", response_body=body, code=(
        'SSI_AUTH_FAILED' if status in (401,403) or code in (401,403,'401','403') else
        'SSI_RATE_LIMIT' if status == 429 or code in (429,'429') else 'SSI_HTTP_ERROR'))
@dataclass
class PageResult:
    items: list[dict]
    pages: int
    raw_pages: list[Any]
    complete: bool = True
    request_params: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    termination: str | None = None

class SSIV3Client:
    def __init__(self, session=None, timeout=30, max_attempts=3, page_size=1000):
        self.session=session or requests.Session(); self.timeout=timeout; self.max_attempts=max(1,min(max_attempts,5)); self.page_size=page_size; self.token=None
    def _request(self, method, path, *, params=None, payload=None, auth=True, master_snapshot=False):
        headers={'Accept':'application/json'}
        if auth:
            if not self.token:self.login()
            headers['Authorization']=f'Bearer {self.token}'
        url=f'{BASE}{path}'
        for attempt in range(1,self.max_attempts+1):
            try:r=self.session.request(method,url,params=params,json=payload,headers=headers,timeout=self.timeout)
            except (requests.Timeout,requests.ConnectionError) as exc:
                if attempt==self.max_attempts:
                    raise SSIReadError(f'network failure for {path}', code=(
                        'SSI_TIMEOUT' if isinstance(exc, requests.Timeout) else 'SSI_NETWORK_ERROR')) from None
                time.sleep(.05*attempt); continue
            except requests.RequestException:
                if not master_snapshot:
                    raise
                raise SSIReadError('Incomplete master HTTP response', code='SSI_BODY_INCOMPLETE') from None
            if r.status_code in (429,) or r.status_code>=500:
                if attempt<self.max_attempts:
                    delay = master_retry_delay(r, attempt) if master_snapshot else .05*attempt
                    if delay is not None:
                        time.sleep(delay); continue
            if master_snapshot and r.status_code != 200:
                raise SSIReadError('Master HTTP request failed', code=(
                    'SSI_AUTH_FAILED' if r.status_code in (401,403) else
                    'SSI_RATE_LIMIT' if r.status_code == 429 else 'SSI_HTTP_ERROR'))
            if r.status_code>=400:
                try: error_body=r.json()
                except ValueError: error_body=getattr(r, "text", None)
                raise _request_error(method, path, params, r.status_code, error_body)
            try:
                if master_snapshot:
                    if len(r.content) > 16 * 1024 * 1024:
                        raise SSIReadError('Master response too large', code='SSI_BODY_LIMIT')
                    # Parse original bytes, never route exact numbers through float.
                    body=json.loads(r.content, parse_float=Decimal,
                                    parse_constant=reject_json_constant,
                                    object_pairs_hook=unique_json_object)
                else:
                    body=r.json()
            except ValueError as exc:
                if master_snapshot:
                    raise SSIReadError('Malformed master JSON response', code='SSI_MALFORMED_JSON') from None
                raise SSIReadError(f'non-JSON SSI response for {path}', response_body=getattr(r, 'text', None)) from exc
            if master_snapshot and not isinstance(body, list):
                code, _ = _envelope_error(body)
                raise SSIReadError('Master response must be an array', code=(
                    'SSI_AUTH_FAILED' if code in (401,403,'401','403') else
                    'SSI_RATE_LIMIT' if code in (429,'429') else
                    'SSI_API_ERROR' if code not in (None,0,'0',200,'200') else 'SSI_INVALID_ENVELOPE'))
            if isinstance(body,dict):
                code,message=_envelope_error(body)
                ohlc_terminal_candidate = (method == 'GET' and path == '/data/ohlc'
                                           and isinstance(params, dict) and params.get('timeFrame') == '1m'
                                           and code in (204, '204'))
                if not ohlc_terminal_candidate and code not in (None,0,'0',200,'200','SUCCESS','success'):
                    raise _request_error(method, path, params, r.status_code, body)
            return body
        raise SSIReadError(f'retry limit reached for {path}')
    def login(self):
        if not config.SSI_API_KEY or not config.SSI_API_SECRET: raise SSIReadError('Missing SSI_API_KEY/SSI_API_SECRET for ssi_v3', code='SSI_CONFIGURATION')
        body=self._request('POST','/auth/token',payload={'apiKey':config.SSI_API_KEY,'apiSecret':config.SSI_API_SECRET},auth=False)
        def find(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if k.casefold() in ('accesstoken','token') and x:return str(x)
                for x in v.values():
                    z=find(x)
                    if z:return z
        self.token=find(body)
        if not self.token:raise SSIReadError('authentication response omitted access token', code='SSI_AUTH_INVALID_RESPONSE')
    @staticmethod
    def _items(body):
        if isinstance(body,list):return body
        if not isinstance(body,dict):return []
        for key in ('data','items','result'):
            value=next((v for k,v in body.items() if k.casefold()==key),None)
            if isinstance(value,list):return value
            if isinstance(value,dict):
                nested=SSIV3Client._items(value)
                if nested:return nested
        return []
    def paged(self,path,params):
        all_items=[]; raw=[]; seen=set()
        for page in range(1,1001):
            query={**params,'pageIndex':page,'pageSize':self.page_size}; body=self._request('GET',path,params=query); raw.append(body); items=self._items(body)
            signature=repr(items)
            if items and signature in seen:raise SSIReadError(f'pagination loop detected for {path}')
            seen.add(signature); all_items.extend(items)
            if not items or len(items)<self.page_size:return PageResult(all_items,page,raw)
        raise SSIReadError(f'pagination was truncated for {path}')
    def securities_summary(self,symbol,date):
        params=securities_summary_params(symbol,date,page_size=self.page_size)
        return self.paged('/data/securitiesSummary',params)
    def masterdata(self,date):return self.paged('/data/masterdata',{'from':date,'to':date})
    def securities_by_board(self, board):
        """Owner-verified unpaginated array contract; no invented paging params."""
        if board not in ('HOSE', 'HNX', 'UPCOM'):
            raise ValueError('Unsupported master board')
        return self._request('GET', '/data/securitiesByBoard', params={'board': board}, master_snapshot=True)
    def ohlc_1m(self, symbol, date, to_date=None, *, page_index=1, page_size=None,
                max_pages=100, ascending=None):
        """Read a bounded 1m preview. Request semantics remain provisional, not production-ready.

        Bounds cover complete inclusive Vietnam calendar days. Without documented
        totals, fetch until an explicit empty page (never stop at a short page).
        Errors retain all received pages in IntradayReadError.result.
        """
        size = self.page_size if page_size is None else page_size
        params = ohlc_1m_params(symbol, date, to_date, page_index=page_index,
                                page_size=size, ascending=ascending)
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 1000:
            raise ValueError("max_pages must be between 1 and 1000")
        result = PageResult([], 0, [], complete=False)
        seen_pages = set()
        expected_total = expected_pages = None
        for current in range(page_index, page_index + max_pages):
            query = {**params, 'pageIndex': current}
            result.request_params.append(query)
            result.pages += 1
            try:
                body = self._request('GET', '/data/ohlc', params=query)
            except (SSIReadError, requests.RequestException) as exc:
                if getattr(exc, 'response_body', None) is not None:
                    result.raw_pages.append(exc.response_body)
                message = str(exc)
                for secret in (self.token, config.SSI_API_KEY, config.SSI_API_SECRET):
                    if secret:
                        message = message.replace(str(secret), '[REDACTED]')
                result.diagnostics.append({'code': 'REQUEST_FAILED', 'page': current, 'message': message})
                raise IntradayReadError(message, result) from None
            result.raw_pages.append(body)
            try:
                items, metadata = ohlc_page(body)
            except SSIReadError as exc:
                result.diagnostics.append({'code': 'MALFORMED_RESPONSE', 'page': current, 'message': str(exc)})
                raise IntradayReadError(str(exc), result) from None
            # Preserve even repeated or structurally invalid candle objects.
            result.items.extend(items)
            signature = json.dumps(sorted(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in items))
            error = None
            total, pages = metadata.get('totalRecord'), metadata.get('pagesCount')
            if metadata.get('pageIndex', current) != current:
                error = 'response pageIndex differs from requested page'
            elif total is not None and expected_total is not None and total != expected_total:
                error = 'provider totalRecord changed across pages'
            elif pages is not None and expected_pages is not None and pages != expected_pages:
                error = 'provider pagesCount changed across pages'
            elif items and signature in seen_pages:
                error = 'pagination loop: repeating page'
            if total is not None:
                expected_total = total
            if pages is not None:
                expected_pages = pages
            if error is None and expected_pages == 0 and items:
                error = 'nonempty page with pagesCount zero'
            if error is None and expected_total is not None and page_index == 1 and len(result.items) > expected_total:
                error = 'received rows exceed provider totalRecord'
            terminal = not items or (expected_pages is not None and current >= expected_pages)
            if error is None and terminal and expected_total is not None and page_index == 1 and len(result.items) != expected_total:
                error = 'truncated pagination: received rows differ from totalRecord'
            if error is None and not items and expected_pages is not None and current < expected_pages:
                error = 'truncated pagination: empty page before pagesCount'
            if error:
                result.diagnostics.append({'code': 'PAGINATION_ERROR', 'page': current, 'message': error})
                raise IntradayReadError(error, result)
            seen_pages.add(signature)
            if terminal:
                result.complete = True
                result.termination = metadata.get('_termination_reason') or ('provider_pagesCount' if items else 'explicit_empty_page')
                return result
        result.diagnostics.append({'code': 'PAGE_LIMIT', 'message': 'pagination truncated at max_pages'})
        raise IntradayReadError('pagination truncated at max_pages', result)
    def index_summary(self,index,date):
        body=self._request('GET','/data/indexSummary',params={'index':index,'tradingDate':provider_date(date)}); return PageResult(self._items(body),1,[body])


class IntradayReadError(SSIReadError):
    """Failed/truncated preview with already received source evidence attached."""

    def __init__(self, message: str, result: PageResult):
        super().__init__(message)
        self.result = result


def ohlc_1m_params(symbol: str, from_date: str, to_date: str | None = None, *,
                    page_index: int = 1, page_size: int = 1000,
                    ascending: bool | None = None) -> dict[str, Any]:
    """One candidate v3 request builder; no retired endpoint/parameter fallbacks."""
    from src.contracts.transforms import to_symbol

    start, end = provider_date(from_date), provider_date(to_date or from_date)
    if start > end:
        raise ValueError('from_date must be on or before to_date')
    for name, value in (('page_index', page_index), ('page_size', page_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    if ascending is not None and not isinstance(ascending, bool):
        raise ValueError('ascending must be a boolean')
    result = {'symbol': to_symbol(symbol, {}), 'from': start + ' 00:00:00',
              'to': end + ' 23:59:59', 'timeFrame': '1m',
              'pageIndex': page_index, 'pageSize': page_size}
    if ascending is not None:
        result['ascending'] = ascending
    return result


def ohlc_page(body: Any) -> tuple[list[Any], dict[str, Any]]:
    """Strict OHLC envelopes: recognize verified 204, never turn other errors into no-data.

    Array key names come from existing repository inspector contracts. The owner
    supplied real 204/No Content evidence separately. Metadata is envelope-only.
    """
    if isinstance(body, list):
        return body, {}
    if not isinstance(body, dict):
        raise SSIReadError('OHLC response must contain a data array')
    metadata: dict[str, Any] = {}
    current = body
    for _ in range(4):
        lower = {str(k).casefold(): v for k, v in current.items()}
        code = next((lower[k] for k in ('code', 'responsecode', 'statuscode', 'errorcode') if k in lower), None)
        terminal_204 = ohlc_no_content_204(current)
        if not terminal_204 and (lower.get('success') is False or lower.get('status') in ('failed', 'error', 'FAILED')
                or lower.get('error') not in (None, '', False, [], {})
                or code not in (None, 0, '0', '00', 200, '200', 'SUCCESS', 'success')):
            raise SSIReadError('OHLC provider envelope reports failure')
        for name in ('pageIndex', 'pageSize', 'pagesCount', 'totalRecord', 'itemsCount'):
            if name.casefold() not in lower:
                continue
            value = lower[name.casefold()]
            if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
                raise SSIReadError(f'invalid pagination metadata: {name}')
            value = int(value)
            if name in metadata and metadata[name] != value:
                raise SSIReadError(f'conflicting pagination metadata: {name}')
            metadata[name] = value
        if terminal_204:
            metadata['_termination_reason'] = 'provider_no_content_204'
            return [], metadata
        arrays = [lower[key] for key in ('data', 'items', 'datalist', 'result') if isinstance(lower.get(key), list)]
        if len(arrays) > 1:
            raise SSIReadError('ambiguous OHLC data arrays')
        if arrays:
            return arrays[0], metadata
        nested = [lower[key] for key in ('data', 'result', 'response') if isinstance(lower.get(key), dict)]
        if len(nested) != 1:
            break
        current = nested[0]
    raise SSIReadError('OHLC response omitted a recognized data array')


def ohlc_no_content_204(body: Any) -> bool:
    """Recognize only the owner-verified OHLC terminal envelope, never generic errors."""
    if not isinstance(body, dict):
        return False
    lower = {str(k).casefold(): v for k, v in body.items()}
    code = lower.get('code')
    if code not in (204, '204'):
        return False
    if type(code) not in (int, str):
        raise SSIReadError('malformed OHLC 204 code')
    messages = [lower[k] for k in ('msg', 'message') if k in lower]
    if not messages or any(not isinstance(m, str) or m.strip().casefold() != 'no content' for m in messages):
        raise SSIReadError('OHLC 204 requires No Content message')
    if (lower.get('success') is False or lower.get('status') not in (None, '', 'success', 'SUCCESS', 'ok', 'OK')
            or lower.get('error') not in (None, '', False, [], {})
            or any(lower[k] not in (0, '0', '00', 200, '200', 204, '204')
                   for k in ('errorcode', 'statuscode', 'responsecode') if k in lower)):
        raise SSIReadError('conflicting OHLC 204 error markers')
    payload_keys = {'data', 'items', 'datalist', 'result', 'response'}
    allowed = payload_keys | {'code', 'msg', 'message', 'success', 'status', 'error',
                              'errorcode', 'statuscode', 'responsecode', 'pageindex',
                              'pagesize', 'pagescount', 'totalrecord', 'itemscount'}
    if set(lower) - allowed or any(lower[k] not in (None, [], {}) for k in payload_keys if k in lower):
        raise SSIReadError('conflicting or unsupported payload in OHLC 204 response')
    return True
