"""Bounded, read-only SSI v3 REST client (no database dependencies)."""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any
import requests
from src.config import config

BASE = "https://api.ssi.com.vn/api/v3"
class SSIReadError(RuntimeError): pass
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
            if r.status_code>=400: raise SSIReadError(f'SSI HTTP {r.status_code} for {path}')
            try:
                body=r.json()
            except ValueError as exc: raise SSIReadError(f'non-JSON SSI response for {path}') from exc
            if isinstance(body,dict):
                code=next((v for k,v in body.items() if k.casefold() in ('code','statuscode','errorcode')),None)
                message=next((v for k,v in body.items() if k.casefold() in ('message','msg','error')),None)
                if code not in (None,0,'0',200,'200','SUCCESS','success'):
                    raise SSIReadError(f'SSI API error for {path}: code={code!r} message={message!r}')
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
    def securities_summary(self,symbol,date):return self.paged('/data/securitiesSummary',{'symbol':symbol,'from':date,'to':date})
    def masterdata(self,date):return self.paged('/data/masterdata',{'from':date,'to':date})
    def ohlc_1m(self,symbol,date):return self.paged('/data/ohlc',{'symbol':symbol,'from':date+' 00:00:00','to':date+' 23:59:59','timeFrame':'1m'})
    def index_summary(self,index,date):
        body=self._request('GET','/data/indexSummary',params={'index':index,'tradingDate':date}); return PageResult(self._items(body),1,[body])
