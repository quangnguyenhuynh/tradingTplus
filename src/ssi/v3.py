"""Bounded, read-only SSI v3 REST client (no database dependencies)."""
from __future__ import annotations
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import requests
from src.config import config

BASE = "https://api.ssi.com.vn/api/v3"
class SSIReadError(RuntimeError): pass


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
    return SSIReadError(f"SSI request failed: {detail}")
@dataclass
class PageResult:
    items: list[dict]
    pages: int
    raw_pages: list[Any]
    complete: bool = True

class SSIV3Client:
    def __init__(self, session=None, timeout=30, max_attempts=3, page_size=1000):
        self.session=session or requests.Session(); self.timeout=timeout; self.max_attempts=max(1,min(max_attempts,5)); self.page_size=page_size; self.token=None
    def _request(self, method, path, *, params=None, payload=None, auth=True):
        headers={'Accept':'application/json'}
        if auth:
            if not self.token:self.login()
            headers['Authorization']=f'Bearer {self.token}'
        url=f'{BASE}{path}'
        for attempt in range(1,self.max_attempts+1):
            try:r=self.session.request(method,url,params=params,json=payload,headers=headers,timeout=self.timeout)
            except (requests.Timeout,requests.ConnectionError) as exc:
                if attempt==self.max_attempts: raise SSIReadError(f'network failure for {path}') from exc
                time.sleep(.05*attempt); continue
            if r.status_code in (429,) or r.status_code>=500:
                if attempt<self.max_attempts: time.sleep(.05*attempt); continue
            if r.status_code>=400:
                try: error_body=r.json()
                except ValueError: error_body=None
                raise _request_error(method, path, params, r.status_code, error_body)
            try:
                body=r.json()
            except ValueError as exc: raise SSIReadError(f'non-JSON SSI response for {path}') from exc
            if isinstance(body,dict):
                code,message=_envelope_error(body)
                if code not in (None,0,'0',200,'200','SUCCESS','success'):
                    raise _request_error(method, path, params, r.status_code, body)
            return body
        raise SSIReadError(f'retry limit reached for {path}')
    def login(self):
        if not config.SSI_API_KEY or not config.SSI_API_SECRET: raise SSIReadError('Missing SSI_API_KEY/SSI_API_SECRET for ssi_v3')
        body=self._request('POST','/auth/token',payload={'apiKey':config.SSI_API_KEY,'apiSecret':config.SSI_API_SECRET},auth=False)
        def find(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if k.casefold() in ('accesstoken','token') and x:return str(x)
                for x in v.values():
                    z=find(x)
                    if z:return z
        self.token=find(body)
        if not self.token:raise SSIReadError('authentication response omitted access token')
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
    def ohlc_1m(self,symbol,date):return self.paged('/data/ohlc',{'symbol':symbol,'from':date+' 00:00:00','to':date+' 23:59:59','timeFrame':'1m'})
    def index_summary(self,index,date):
        body=self._request('GET','/data/indexSummary',params={'index':index,'tradingDate':date}); return PageResult(self._items(body),1,[body])
